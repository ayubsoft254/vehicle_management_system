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
    
    context = {
        'report': report,
        'recent_executions': recent_executions,
        'is_saved': SavedReport.objects.filter(user=request.user, report=report).exists(),
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
    """Main reports dashboard"""
    
    user_reports = Report.objects.filter(
        Q(created_by=request.user) |
        Q(is_public=True) |
        Q(allowed_users=request.user)
    ).distinct()
    
    context = {
        'total_reports': user_reports.count(),
        'scheduled_reports': user_reports.filter(is_scheduled=True).count(),
        'recent_executions': ReportExecution.objects.filter(
            report__in=user_reports
        ).order_by('-created_at')[:10],
        'popular_reports': user_reports.order_by('-execution_count')[:5],
        'saved_reports_count': SavedReport.objects.filter(user=request.user).count(),
    }
    
    return render(request, 'reports/dashboard.html', context)


# ============================================================================
# REPORT BUILDER
# ============================================================================

@login_required
@permission_required('reports.add_report')
def report_builder(request):
    """Interactive report builder"""
    
    if request.method == 'POST':
        form = QuickReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user
            report.save()
            
            messages.success(request, 'Report created successfully.')
            return redirect('reports:report_detail', pk=report.pk)
    else:
        form = QuickReportForm()
    
    context = {
        'form': form,
        'templates': ReportTemplate.objects.filter(is_active=True),
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
    
    types = [{'value': t[0], 'label': t[1]} for t in Report.REPORT_TYPE_CHOICES]
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