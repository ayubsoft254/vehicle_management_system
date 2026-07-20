"""
Reports App - Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from datetime import timedelta
import json
import os

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import inch

from .models import (
    Report,
    ReportTemplate,
    ReportExecution,
    ReportWidget,
    SavedReport
)
from .forms import (
    ReportForm,
    ReportFilterForm,
    ReportTemplateForm,
    ReportWidgetForm,
    QuickReportForm
)


DEFAULT_REPORT_TEMPLATE_NAME = 'Universal Executive Template'


def ensure_default_report_template():
    """Create a single reusable default template for the report builder."""
    template, created = ReportTemplate.objects.get_or_create(
        name=DEFAULT_REPORT_TEMPLATE_NAME,
        defaults={
            'description': 'Default polished template for all quick reports.',
            'report_type': 'custom',
            'layout': 'executive',
            'columns': ['date', 'reference', 'category', 'amount', 'status'],
            'grouping': {'by': 'date'},
            'sorting': {'field': 'date', 'direction': 'desc'},
            'aggregations': ['count', 'sum'],
            'is_active': True,
            'header_template': 'Vehicle Management System - Executive Report',
            'footer_template': 'Generated automatically by Report Builder',
            'css_styles': '.report-title{font-weight:700;color:#1f2937;} .summary-card{border:1px solid #e5e7eb;}',
        },
    )

    if not created and not template.is_active:
        template.is_active = True
        template.save(update_fields=['is_active'])

    return template


# ============================================================================
# REPORT LIST & DETAIL VIEWS
# ============================================================================

@login_required
def report_list(request):
    """Display list of reports"""
    
    reports = Report.objects.filter(is_active=True)
    
    # Filter by user access
    if not request.user.is_staff:
        reports = reports.filter(
            Q(created_by=request.user) |
            Q(is_public=True) |
            Q(allowed_users=request.user)
        ).distinct()
    
    # Apply filters
    filter_form = ReportFilterForm(request.GET)
    if filter_form.is_valid():
        report_type = filter_form.cleaned_data.get('report_type')
        if report_type:
            reports = reports.filter(report_type=report_type)
        
        search = filter_form.cleaned_data.get('search')
        if search:
            reports = reports.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
    
    # Pagination
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reports': page_obj,
        'filter_form': filter_form,
        'total_reports': reports.count(),
        'scheduled_reports': reports.filter(is_scheduled=True).count(),
    }
    
    return render(request, 'reports/report_list.html', context)


@login_required
def report_detail(request, pk):
    """View report details"""
    
    report = get_object_or_404(Report, pk=pk)
    
    # Check access
    if not report.can_user_access(request.user):
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('reports:report_list')
    
    # Get recent executions
    recent_executions = report.executions.order_by('-created_at')[:10]

    email_recipients_list = [
        email.strip()
        for email in (report.email_recipients or '').split(',')
        if email.strip()
    ]
    
    context = {
        'report': report,
        'recent_executions': recent_executions,
        'is_saved': SavedReport.objects.filter(user=request.user, report=report).exists(),
        'email_recipients_list': email_recipients_list,
    }
    
    return render(request, 'reports/report_detail.html', context)


# ============================================================================
# REPORT CRUD VIEWS
# ============================================================================

class ReportCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create new report"""
    model = Report
    form_class = ReportForm
    template_name = 'reports/report_form.html'
    permission_required = 'reports.add_report'
    success_url = reverse_lazy('reports:report_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Report created successfully.')
        return super().form_valid(form)


class ReportUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update existing report"""
    model = Report
    form_class = ReportForm
    template_name = 'reports/report_form.html'
    permission_required = 'reports.change_report'
    
    def get_success_url(self):
        return reverse_lazy('reports:report_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Report updated successfully.')
        return super().form_valid(form)


class ReportDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete report"""
    model = Report
    template_name = 'reports/report_confirm_delete.html'
    permission_required = 'reports.delete_report'
    success_url = reverse_lazy('reports:report_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Report deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# REPORT EXECUTION VIEWS
# ============================================================================

@login_required
@require_POST
def run_report(request, pk):
    """Execute a report"""
    
    report = get_object_or_404(Report, pk=pk)
    
    # Check access
    if not report.can_user_access(request.user):
        messages.error(request, 'You do not have permission to run this report.')
        return redirect('reports:report_list')
    
    # Create execution record
    execution = ReportExecution.objects.create(
        report=report,
        triggered_by=request.user,
        is_scheduled=False,
        output_format=report.output_format,
        date_from=report.get_date_range()[0],
        date_to=report.get_date_range()[1]
    )
    
    # Queue execution task
    from .tasks import execute_report_task
    execute_report_task.delay(str(execution.id))
    
    messages.success(request, 'Report queued for execution.')
    return redirect('reports:execution_detail', pk=execution.pk)


@login_required
def execution_detail(request, pk):
    """View execution details"""
    
    execution = get_object_or_404(ReportExecution, pk=pk)
    
    # Check access
    if not execution.report.can_user_access(request.user):
        messages.error(request, 'You do not have permission to view this execution.')
        return redirect('reports:report_list')
    
    context = {
        'execution': execution,
    }
    
    return render(request, 'reports/execution_detail.html', context)


@login_required
def download_report(request, pk):
    """Download generated report file"""
    
    execution = get_object_or_404(ReportExecution, pk=pk)
    
    # Check access
    if not execution.report.can_user_access(request.user):
        messages.error(request, 'You do not have permission to download this report.')
        return redirect('reports:report_list')
    
    if execution.status != 'completed' or not execution.file_path:
        messages.error(request, 'Report file is not available.')
        return redirect('reports:execution_detail', pk=pk)
    
    # Check if file exists
    if not os.path.exists(execution.file_path):
        messages.error(request, 'Report file not found.')
        return redirect('reports:execution_detail', pk=pk)
    
    # Determine content type
    content_types = {
        'pdf': 'application/pdf',
        'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv': 'text/csv',
        'json': 'application/json',
        'html': 'text/html',
    }
    content_type = content_types.get(execution.output_format, 'application/octet-stream')
    
    # Get filename
    filename = f"{execution.report.name}_{execution.created_at.strftime('%Y%m%d_%H%M%S')}.{execution.output_format}"
    
    response = FileResponse(open(execution.file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def execution_list(request):
    """List all report executions"""
    
    executions = ReportExecution.objects.select_related('report', 'triggered_by').order_by('-created_at')
    
    # Filter by user access
    if not request.user.is_staff:
        executions = executions.filter(
            Q(triggered_by=request.user) |
            Q(report__created_by=request.user) |
            Q(report__is_public=True) |
            Q(report__allowed_users=request.user)
        ).distinct()
    
    # Filters
    status = request.GET.get('status')
    if status:
        executions = executions.filter(status=status)
    
    report_id = request.GET.get('report')
    if report_id:
        executions = executions.filter(report_id=report_id)
    
    # Pagination
    paginator = Paginator(executions, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'executions': page_obj,
    }
    
    return render(request, 'reports/execution_list.html', context)


# ============================================================================
# REPORT TEMPLATES
# ============================================================================

class ReportTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ReportTemplate
    template_name = 'reports/template_list.html'
    context_object_name = 'templates'
    permission_required = 'reports.view_reporttemplate'
    paginate_by = 20


class ReportTemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ReportTemplate
    form_class = ReportTemplateForm
    template_name = 'reports/template_form.html'
    permission_required = 'reports.add_reporttemplate'
    success_url = reverse_lazy('reports:template_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Template created successfully.')
        return super().form_valid(form)


class ReportTemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ReportTemplate
    form_class = ReportTemplateForm
    template_name = 'reports/template_form.html'
    permission_required = 'reports.change_reporttemplate'
    success_url = reverse_lazy('reports:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Template updated successfully.')
        return super().form_valid(form)


class ReportTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ReportTemplate
    template_name = 'reports/template_confirm_delete.html'
    permission_required = 'reports.delete_reporttemplate'
    success_url = reverse_lazy('reports:template_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Template deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# SAVED REPORTS
# ============================================================================

@login_required
@require_POST
def save_report(request, pk):
    """Save report to user's favorites"""
    
    report = get_object_or_404(Report, pk=pk)
    
    saved, created = SavedReport.objects.get_or_create(
        user=request.user,
        report=report
    )
    
    if created:
        messages.success(request, 'Report saved to favorites.')
    else:
        messages.info(request, 'Report already in favorites.')
    
    return redirect('reports:report_detail', pk=pk)


@login_required
@require_POST
def unsave_report(request, pk):
    """Remove report from user's favorites"""
    
    report = get_object_or_404(Report, pk=pk)
    
    deleted = SavedReport.objects.filter(user=request.user, report=report).delete()[0]
    
    if deleted:
        messages.success(request, 'Report removed from favorites.')
    
    return redirect('reports:report_detail', pk=pk)


@login_required
def my_reports(request):
    """View user's saved reports"""
    
    saved_reports = SavedReport.objects.filter(user=request.user).select_related('report')
    
    context = {
        'saved_reports': saved_reports,
    }
    
    return render(request, 'reports/my_reports.html', context)


# ============================================================================
# REPORT WIDGETS
# ============================================================================

@login_required
def widget_list(request):
    """Display report widgets dashboard"""
    
    widgets = ReportWidget.objects.filter(is_active=True)
    
    # Filter by user access
    if not request.user.is_staff:
        widgets = widgets.filter(
            Q(is_public=True) |
            Q(allowed_users=request.user)
        ).distinct()
    
    widgets = widgets.order_by('order')
    
    context = {
        'widgets': widgets,
    }
    
    return render(request, 'reports/widget_dashboard.html', context)


@login_required
def widget_data(request, pk):
    """Get widget data (AJAX)"""
    
    widget = get_object_or_404(ReportWidget, pk=pk)
    
    # Check access
    if not widget.is_public and not request.user.is_staff:
        if request.user not in widget.allowed_users.all():
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Generate widget data
    from .utils import generate_widget_data
    data = generate_widget_data(widget)
    
    return JsonResponse(data)


# ============================================================================
# REPORT DASHBOARD
# ============================================================================

@login_required
def report_dashboard(request):
    """Report Center: a single categorized index of every standard business
    report in the system, each a direct filter-and-generate page that
    exports to PDF/Excel/CSV."""
    from django.urls import reverse

    def link(name, *args):
        try:
            return reverse(name, args=args)
        except Exception:
            return '#'

    report_sections = [
        {
            'heading': 'Financial',
            'items': [
                {'title': 'Financial Overview', 'description': 'Sales, collections, commissions and payouts across the business.', 'icon': 'fa-chart-line', 'url': link('reports:financial_reports')},
                {'title': 'Main Ledger', 'description': 'Every money-in / money-out transaction across all sub-ledgers.', 'icon': 'fa-book-open', 'url': link('vehicles:main_ledger')},
                {'title': 'Defaulters Report', 'description': 'Clients with overdue balances, ranked by days overdue.', 'icon': 'fa-exclamation-triangle', 'url': link('payments:defaulters_report')},
            ],
        },
        {
            'heading': 'Clients & Vehicles',
            'items': [
                {'title': 'Client Ledger', 'description': 'What every client owes and has paid across their purchases.', 'icon': 'fa-users', 'url': link('clients:client_ledger_list')},
                {'title': 'Vehicle Inventory', 'description': 'Stock, status and valuation across the fleet.', 'icon': 'fa-car', 'url': link('vehicles:vehicle_reports')},
            ],
        },
        {
            'heading': 'Business Partner Ledgers',
            'items': [
                {'title': 'Broker Ledger', 'description': 'Commission earned and paid out per broker.', 'icon': 'fa-user-tie', 'url': link('vehicles:broker_ledger_list')},
                {'title': 'Tracker Agent Ledger', 'description': 'Amounts owed and paid to tracker installation agents.', 'icon': 'fa-satellite-dish', 'url': link('vehicles:tracker_agent_ledger_list')},
                {'title': 'Clearing Agent Ledger', 'description': 'Amounts owed and paid to clearing agents.', 'icon': 'fa-ship', 'url': link('vehicles:clearing_agent_ledger_list')},
                {'title': 'Japan Supplier Ledger', 'description': 'Purchases and payments to Japan suppliers.', 'icon': 'fa-store', 'url': link('vehicles:japan_supplier_ledger_list')},
                {'title': 'Insurance Agent Ledger', 'description': 'Amounts owed and paid to insurance agents.', 'icon': 'fa-handshake', 'url': link('insurance:agent_ledger_list')},
                {'title': 'Business Loans', 'description': 'Money loaned out by the business and repayment status.', 'icon': 'fa-hand-holding-usd', 'url': link('vehicles:business_loan_list')},
            ],
        },
        {
            'heading': 'Expenses & Payroll',
            'items': [
                {'title': 'Expense Report', 'description': 'Spending by category, status and vendor.', 'icon': 'fa-receipt', 'url': link('expenses:expense_report')},
                {'title': 'Payroll Report', 'description': 'Gross pay, deductions and net pay by period.', 'icon': 'fa-money-check-alt', 'url': link('payroll:payroll_reports')},
            ],
        },
        {
            'heading': 'Insurance',
            'items': [
                {'title': 'Insurance Analytics', 'description': 'Policy volume, premiums and claims overview.', 'icon': 'fa-shield-alt', 'url': link('insurance:insurance_reports')},
            ],
        },
        {
            'heading': 'Operations',
            'items': [
                {'title': 'Auctions Report', 'description': 'Auction activity, bids and results.', 'icon': 'fa-gavel', 'url': link('auctions:auction_report')},
                {'title': 'Repossessions Report', 'description': 'Repossession cases, status and recovered value.', 'icon': 'fa-truck-loading', 'url': link('repossessions:repossession_reports')},
                {'title': 'Documents Report', 'description': 'Document volume by category and signature status.', 'icon': 'fa-folder-open', 'url': link('documents:document_report')},
            ],
        },
        {
            'heading': 'Compliance',
            'items': [
                {'title': 'Audit Summary', 'description': 'System activity by action, module and user.', 'icon': 'fa-history', 'url': link('audit:report')},
            ],
        },
    ]

    context = {
        'report_sections': report_sections,
    }

    return render(request, 'reports/dashboard.html', context)


# ============================================================================
# REPORT BUILDER
# ============================================================================

@login_required
@permission_required('reports.add_report')
def report_builder(request):
    """Interactive report builder"""
    default_template = ensure_default_report_template()

    
    if request.method == 'POST':
        form = QuickReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            if not report.template_id:
                report.template = default_template
            report.created_by = request.user
            report.save()
            
            messages.success(request, 'Report created successfully.')
            return redirect('reports:report_detail', pk=report.pk)
    else:
        form = QuickReportForm(initial={'template': default_template.pk})

    templates = list(ReportTemplate.objects.filter(is_active=True))
    templates.sort(key=lambda template: (template.pk != default_template.pk, template.name))
    
    context = {
        'form': form,
        'templates': templates,
        'default_template': default_template,
    }
    
    return render(request, 'reports/report_builder.html', context)


# ============================================================================
# REPORT SCHEDULING
# ============================================================================

@login_required
@permission_required('reports.change_report')
@require_POST
def schedule_report(request, pk):
    """Schedule a report"""
    
    report = get_object_or_404(Report, pk=pk)
    
    report.is_scheduled = True
    report.next_run = report.calculate_next_run()
    report.save()
    
    messages.success(request, f'Report scheduled. Next run: {report.next_run}')
    return redirect('reports:report_detail', pk=pk)


@login_required
@permission_required('reports.change_report')
@require_POST
def unschedule_report(request, pk):
    """Unschedule a report"""
    
    report = get_object_or_404(Report, pk=pk)
    
    report.is_scheduled = False
    report.next_run = None
    report.save()
    
    messages.success(request, 'Report unscheduled.')
    return redirect('reports:report_detail', pk=pk)


# ============================================================================
# API ENDPOINTS (JSON)
# ============================================================================

@login_required
def report_types_api(request):
    """Get available report types"""

    types = [
        {'value': t[0], 'label': t[1]}
        for t in Report.REPORT_TYPE_CHOICES
        if t[0] != 'payroll'
    ]
    return JsonResponse({'types': types})


@login_required
def report_stats_api(request, pk):
    """Get report statistics"""
    
    report = get_object_or_404(Report, pk=pk)
    
    if not report.can_user_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    stats = {
        'execution_count': report.execution_count,
        'average_execution_time': float(report.average_execution_time) if report.average_execution_time else 0,
        'last_execution_status': report.last_execution_status,
        'last_run': report.last_run.isoformat() if report.last_run else None,
        'success_rate': 0,
    }
    
    # Calculate success rate
    total = report.executions.count()
    if total > 0:
        successful = report.executions.filter(status='completed').count()
        stats['success_rate'] = (successful / total) * 100
    
    return JsonResponse(stats)


@login_required
def execution_status_api(request, pk):
    """Get execution status (AJAX polling)"""
    
    execution = get_object_or_404(ReportExecution, pk=pk)
    
    if not execution.report.can_user_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    data = {
        'id': str(execution.id),
        'status': execution.status,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'execution_time': float(execution.execution_time) if execution.execution_time else None,
        'row_count': execution.row_count,
        'error_message': execution.error_message,
        'can_download': execution.status == 'completed' and bool(execution.file_path),
    }
    
    return JsonResponse(data)


# ============================================================================
# ANALYTICS
# ============================================================================

@login_required
@permission_required('reports.view_report')
def report_analytics(request):
    """View reporting analytics"""
    
    # Get date range
    days = int(request.GET.get('days', 30))
    cutoff = timezone.now() - timedelta(days=days)
    
    executions = ReportExecution.objects.filter(created_at__gte=cutoff)
    
    analytics = {
        'total_executions': executions.count(),
        'successful': executions.filter(status='completed').count(),
        'failed': executions.filter(status='failed').count(),
        'average_execution_time': executions.filter(status='completed').aggregate(
            avg=Avg('execution_time')
        )['avg'] or 0,
        'by_type': {},
        'by_status': {},
        'top_reports': [],
    }
    
    # By type
    by_type = executions.values('report__report_type').annotate(count=Count('id'))
    for item in by_type:
        analytics['by_type'][item['report__report_type']] = item['count']
    
    # By status
    by_status = executions.values('status').annotate(count=Count('id'))
    for item in by_status:
        analytics['by_status'][item['status']] = item['count']
    
    # Top reports
    top_reports = Report.objects.order_by('-execution_count')[:10]
    analytics['top_reports'] = [
        {'name': r.name, 'count': r.execution_count}
        for r in top_reports
    ]
    
    context = {
        'analytics': analytics,
        'days': days,
    }
    
    return render(request, 'reports/analytics.html', context)


# ============================================================================
# FINANCIAL REPORTS
# ============================================================================

def _build_financial_overview_context(date_from=None, date_to=None):
    """Cross-app financial analytics, shared by the on-screen report and its PDF/Excel/CSV exports.

    date_from/date_to scope the sales-related aggregates (sales_agg,
    payment_type_data, top_clients, gross_profit) by ClientVehicle.purchase_date.
    Insurance/tracker/clearance/inventory aggregates stay all-time - they're
    party-level running ledgers with no single "purchase date" of their own.
    """
    from django.db.models import DecimalField, Value, F
    from django.db.models.functions import Coalesce
    from apps.clients.models import ClientVehicle
    from apps.vehicles.models import Vehicle, TrackerRecord, ClearanceRecord
    from apps.insurance.models import InsurancePolicy

    # ---- Sales revenue (sold vehicles via ClientVehicle) ----
    sales_qs = ClientVehicle.objects.filter(vehicle__status='sold')
    if date_from:
        sales_qs = sales_qs.filter(purchase_date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(purchase_date__lte=date_to)
    sales_agg = sales_qs.aggregate(
        total_revenue=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
        total_collected=Coalesce(Sum('total_paid'), Value(0, output_field=DecimalField())),
        total_outstanding=Coalesce(Sum('balance'), Value(0, output_field=DecimalField())),
        total_deposit=Coalesce(Sum('deposit_paid'), Value(0, output_field=DecimalField())),
        total_count=Count('id'),
    )

    # ---- Vehicle inventory cost ----
    vehicles_qs = Vehicle.objects.all()
    inventory_agg = vehicles_qs.aggregate(
        total_purchase_cost=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
        total_selling_value=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
    )

    # ---- Insurance revenue ----
    insurance_agg = InsurancePolicy.objects.aggregate(
        total_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        policy_count=Count('id'),
    )
    insurance_profit = (insurance_agg['total_selling'] or 0) - (insurance_agg['total_buying'] or 0)
    insurance_unpaid = InsurancePolicy.objects.filter(dealer_payment_status='unpaid').aggregate(
        total=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField()))
    )['total'] or 0

    # ---- Tracker revenue ----
    tracker_agg = TrackerRecord.objects.aggregate(
        total_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        record_count=Count('id'),
    )
    tracker_profit = (tracker_agg['total_selling'] or 0) - (tracker_agg['total_buying'] or 0)
    tracker_unpaid = TrackerRecord.objects.filter(dealer_payment_status='unpaid').aggregate(
        total=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField()))
    )['total'] or 0

    # ---- Clearance revenue ----
    clearance_agg = ClearanceRecord.objects.aggregate(
        total_billed=Coalesce(Sum('amount'), Value(0, output_field=DecimalField())),
        record_count=Count('id'),
    )
    clearance_unpaid = ClearanceRecord.objects.filter(payment_status='unpaid').aggregate(
        total=Coalesce(Sum('amount'), Value(0, output_field=DecimalField()))
    )['total'] or 0
    clearance_settled = (clearance_agg['total_billed'] or 0) - clearance_unpaid

    # ---- Payment type breakdown ----
    payment_type_data = []
    for pt_val, pt_label in ClientVehicle.PAYMENT_TYPE_CHOICES:
        qs = sales_qs.filter(payment_type=pt_val)
        agg = qs.aggregate(
            count=Count('id'),
            revenue=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            collected=Coalesce(Sum('total_paid'), Value(0, output_field=DecimalField())),
            outstanding=Coalesce(Sum('balance'), Value(0, output_field=DecimalField())),
        )
        payment_type_data.append({'label': pt_label, **agg})

    # ---- Paid-off vs active ----
    paid_off_count = sales_qs.filter(is_paid_off=True).count()
    active_count = sales_qs.filter(is_paid_off=False, is_active=True).count()

    # ---- This month's collections ----
    today = timezone.now().date()
    month_start = today.replace(day=1)
    this_month_revenue = ClientVehicle.objects.filter(
        vehicle__status='sold',
        purchase_date__gte=month_start,
    ).aggregate(
        count=Count('id'),
        revenue=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
    )

    # ---- Top clients by purchase price ----
    top_clients = (
        ClientVehicle.objects.filter(vehicle__status='sold')
        .select_related('client')
        .values('client__first_name', 'client__last_name', 'client__id')
        .annotate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_paid=Coalesce(Sum('total_paid'), Value(0, output_field=DecimalField())),
            balance=Coalesce(Sum('balance'), Value(0, output_field=DecimalField())),
            vehicle_count=Count('id'),
        )
        .order_by('-total_purchase')[:10]
    )

    # ---- Gross profit estimate (sales revenue - vehicle purchase cost) ----
    gross_profit = (sales_agg['total_revenue'] or 0) - (inventory_agg['total_purchase_cost'] or 0)

    return {
        'sales_agg': sales_agg,
        'inventory_agg': inventory_agg,
        'insurance_agg': insurance_agg,
        'insurance_profit': insurance_profit,
        'insurance_unpaid': insurance_unpaid,
        'tracker_agg': tracker_agg,
        'tracker_profit': tracker_profit,
        'tracker_unpaid': tracker_unpaid,
        'clearance_agg': clearance_agg,
        'clearance_settled': clearance_settled,
        'clearance_unpaid': clearance_unpaid,
        'payment_type_data': payment_type_data,
        'paid_off_count': paid_off_count,
        'active_count': active_count,
        'this_month_revenue': this_month_revenue,
        'top_clients': top_clients,
        'gross_profit': gross_profit,
        'today': today,
        'month_start': month_start,
        'date_from': date_from,
        'date_to': date_to,
    }


@login_required
def financial_reports(request):
    """Cross-app financial overview: sales, collections, commissions and payouts."""
    from django.urls import reverse
    from utils.ledger import parse_date_range
    import urllib.parse

    date_from, date_to = parse_date_range(request)
    context = _build_financial_overview_context(date_from, date_to)
    context['can_see_prices'] = request.user.is_staff
    if date_from or date_to:
        context['report_subtitle'] = f"Sales from {date_from or 'the beginning'} to {date_to or 'today'}"
    else:
        context['report_subtitle'] = f"Cross-portfolio snapshot as of {context['today'].strftime('%d %B %Y')}"
    qs_params = {}
    if date_from:
        qs_params['date_from'] = date_from.isoformat()
    if date_to:
        qs_params['date_to'] = date_to.isoformat()
    filter_qs = urllib.parse.urlencode(qs_params)
    context['filter_qs'] = filter_qs
    context['export_pdf_url'] = reverse('reports:financial_reports_pdf') + ('?' + filter_qs if filter_qs else '')
    context['export_excel_url'] = reverse('reports:financial_reports_excel') + ('?' + filter_qs if filter_qs else '')
    context['export_csv_url'] = reverse('reports:financial_reports_csv') + ('?' + filter_qs if filter_qs else '')
    return render(request, 'reports/financial_reports.html', context)


@login_required
def financial_reports_pdf(request):
    from utils.report_kit import build_pdf_response, styled_table, kpi_table, fmt_money
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    ctx = _build_financial_overview_context(date_from, date_to)

    def body(elements, styles):
        elements.append(Paragraph('Sales Overview', styles['ReportSectionHeading']))
        elements.append(kpi_table([
            ('Total Revenue', fmt_money(ctx['sales_agg']['total_revenue'])),
            ('Total Collected', fmt_money(ctx['sales_agg']['total_collected'])),
            ('Outstanding Balance', fmt_money(ctx['sales_agg']['total_outstanding'])),
            ('Gross Profit (est.)', fmt_money(ctx['gross_profit'])),
            ('Vehicles Sold', str(ctx['sales_agg']['total_count'])),
            ('Fully Paid Off', str(ctx['paid_off_count'])),
        ]))
        elements.append(Spacer(1, 14))

        elements.append(Paragraph('Partner Ledgers', styles['ReportSectionHeading']))
        elements.append(styled_table([
            ['Ledger', 'Billed / Sold', 'Unpaid', 'Profit'],
            ['Insurance', fmt_money(ctx['insurance_agg']['total_selling']), fmt_money(ctx['insurance_unpaid']), fmt_money(ctx['insurance_profit'])],
            ['Tracker', fmt_money(ctx['tracker_agg']['total_selling']), fmt_money(ctx['tracker_unpaid']), fmt_money(ctx['tracker_profit'])],
            ['Clearance', fmt_money(ctx['clearance_agg']['total_billed']), fmt_money(ctx['clearance_unpaid']), '—'],
        ], col_widths=[1.6 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch], align_right_from=1))
        elements.append(Spacer(1, 14))

        elements.append(Paragraph('Top Clients by Purchase Value', styles['ReportSectionHeading']))
        rows = [['Client', 'Vehicles', 'Total Purchase', 'Paid', 'Balance']]
        for c in ctx['top_clients']:
            rows.append([
                f"{c['client__first_name']} {c['client__last_name']}",
                str(c['vehicle_count']),
                fmt_money(c['total_purchase']),
                fmt_money(c['total_paid']),
                fmt_money(c['balance']),
            ])
        elements.append(styled_table(rows, col_widths=[1.8 * inch, 0.8 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch], align_right_from=1))

    if date_from or date_to:
        subtitle = f"Sales from {date_from or 'the beginning'} to {date_to or 'today'}"
    else:
        subtitle = f"As at {ctx['today'].strftime('%d %B %Y')}"

    return build_pdf_response(
        'financial_overview.pdf', 'Financial Overview',
        subtitle=subtitle, build_body=body,
    )


@login_required
def financial_reports_excel(request):
    from utils.report_kit import build_excel_response
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    ctx = _build_financial_overview_context(date_from, date_to)
    headers = ['Client', 'Vehicles', 'Total Purchase', 'Paid', 'Balance']
    rows = [
        [f"{c['client__first_name']} {c['client__last_name']}", c['vehicle_count'], float(c['total_purchase']), float(c['total_paid']), float(c['balance'])]
        for c in ctx['top_clients']
    ]
    return build_excel_response('financial_overview.xlsx', 'Top Clients', headers, rows, currency_cols={3, 4, 5})


@login_required
def financial_reports_csv(request):
    from utils.report_kit import build_csv_response
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    ctx = _build_financial_overview_context(date_from, date_to)
    headers = ['Client', 'Vehicles', 'Total Purchase', 'Paid', 'Balance']
    rows = [
        [f"{c['client__first_name']} {c['client__last_name']}", c['vehicle_count'], c['total_purchase'], c['total_paid'], c['balance']]
        for c in ctx['top_clients']
    ]
    return build_csv_response('financial_overview.csv', headers, rows)


# ============================================================================
# EXPORT & SHARING
# ============================================================================

@login_required
def export_report_config(request, pk):
    """Export report configuration as JSON"""
    
    report = get_object_or_404(Report, pk=pk)
    
    if not report.can_user_access(request.user):
        messages.error(request, 'Access denied.')
        return redirect('reports:report_list')
    
    config = {
        'name': report.name,
        'description': report.description,
        'report_type': report.report_type,
        'query_config': report.query_config,
        'date_range_type': report.date_range_type,
        'output_format': report.output_format,
        'include_charts': report.include_charts,
        'include_summary': report.include_summary,
        'include_details': report.include_details,
    }
    
    response = HttpResponse(json.dumps(config, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{report.name}_config.json"'
    
    return response