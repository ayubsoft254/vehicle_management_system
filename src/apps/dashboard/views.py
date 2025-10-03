"""
Dashboard App - Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
import json

from .models import (
    Dashboard,
    Widget,
    UserDashboardPreference,
    QuickAction,
    DashboardSnapshot,
    DashboardActivity
)
from .forms import (
    DashboardForm,
    QuickDashboardForm,
    WidgetForm,
    QuickWidgetForm,
    UserDashboardPreferenceForm,
    QuickActionForm,
    DashboardSnapshotForm,
    ShareDashboardForm
)
from .utils import (
    get_dashboard_overview_data,
    get_financial_summary,
    get_sales_metrics,
    get_auction_metrics,
    get_widget_data,
    log_dashboard_activity
)
from .widgets import (
    create_dashboard_from_template,
    get_all_widget_templates,
    create_widget_from_template
)


# ============================================================================
# MAIN DASHBOARD VIEW
# ============================================================================

@login_required
def dashboard_home(request):
    """Main dashboard view"""
    
    # Get or create user preferences
    preference, created = UserDashboardPreference.objects.get_or_create(user=request.user)
    
    # Get default dashboard
    if preference.default_dashboard:
        dashboard = preference.default_dashboard
    else:
        # Get first accessible dashboard or default
        dashboard = Dashboard.objects.filter(
            Q(created_by=request.user) |
            Q(is_public=True) |
            Q(is_default=True) |
            Q(shared_with=request.user)
        ).first()
    
    if not dashboard:
        # Create default dashboard for user
        from .widgets import create_dashboard_from_template
        dashboard = create_dashboard_from_template(request.user, 'executive')
        preference.default_dashboard = dashboard
        preference.save()
    
    # Log activity
    log_dashboard_activity(dashboard, request.user, 'view')
    
    # Get dashboard data
    context = {
        'dashboard': dashboard,
        'widgets': dashboard.widgets.filter(is_active=True).order_by('order'),
        'preference': preference,
        'overview_data': get_dashboard_overview_data(request.user),
    }
    
    return render(request, 'dashboard/dashboard_home.html', context)


@login_required
def dashboard_detail(request, pk):
    """View specific dashboard"""
    
    dashboard = get_object_or_404(Dashboard, pk=pk)
    
    # Check access
    if not dashboard.can_user_access(request.user):
        messages.error(request, 'You do not have permission to view this dashboard.')
        return redirect('dashboard:home')
    
    # Log activity
    log_dashboard_activity(dashboard, request.user, 'view')
    
    context = {
        'dashboard': dashboard,
        'widgets': dashboard.widgets.filter(is_active=True).order_by('order'),
    }
    
    return render(request, 'dashboard/dashboard_detail.html', context)


# ============================================================================
# DASHBOARD CRUD VIEWS
# ============================================================================

class DashboardListView(LoginRequiredMixin, ListView):
    """List all dashboards"""
    model = Dashboard
    template_name = 'dashboard/dashboard_list.html'
    context_object_name = 'dashboards'
    paginate_by = 20
    
    def get_queryset(self):
        return Dashboard.objects.for_user(self.request.user).filter(is_active=True)


class DashboardCreateView(LoginRequiredMixin, CreateView):
    """Create new dashboard"""
    model = Dashboard
    form_class = DashboardForm
    template_name = 'dashboard/dashboard_form.html'
    success_url = reverse_lazy('dashboard:home')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Dashboard created successfully.')
        return response


class DashboardUpdateView(LoginRequiredMixin, UpdateView):
    """Update existing dashboard"""
    model = Dashboard
    form_class = DashboardForm
    template_name = 'dashboard/dashboard_form.html'
    
    def get_success_url(self):
        return reverse_lazy('dashboard:dashboard_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        log_dashboard_activity(self.object, self.request.user, 'layout_changed')
        messages.success(self.request, 'Dashboard updated successfully.')
        return super().form_valid(form)


class DashboardDeleteView(LoginRequiredMixin, DeleteView):
    """Delete dashboard"""
    model = Dashboard
    template_name = 'dashboard/dashboard_confirm_delete.html'
    success_url = reverse_lazy('dashboard:home')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Dashboard deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# WIDGET VIEWS
# ============================================================================

@login_required
def widget_create(request, dashboard_pk):
    """Create new widget"""
    
    dashboard = get_object_or_404(Dashboard, pk=dashboard_pk)
    
    if request.method == 'POST':
        form = WidgetForm(request.POST)
        if form.is_valid():
            widget = form.save(commit=False)
            widget.dashboard = dashboard
            widget.save()
            
            log_dashboard_activity(dashboard, request.user, 'widget_added', f'Added widget: {widget.name}')
            messages.success(request, 'Widget added successfully.')
            return redirect('dashboard:dashboard_detail', pk=dashboard.pk)
    else:
        form = WidgetForm(initial={'dashboard': dashboard})
    
    context = {
        'form': form,
        'dashboard': dashboard,
    }
    
    return render(request, 'dashboard/widget_form.html', context)


@login_required
def widget_update(request, pk):
    """Update existing widget"""
    
    widget = get_object_or_404(Widget, pk=pk)
    
    if request.method == 'POST':
        form = WidgetForm(request.POST, instance=widget)
        if form.is_valid():
            form.save()
            
            log_dashboard_activity(widget.dashboard, request.user, 'widget_updated', f'Updated widget: {widget.name}')
            messages.success(request, 'Widget updated successfully.')
            return redirect('dashboard:dashboard_detail', pk=widget.dashboard.pk)
    else:
        form = WidgetForm(instance=widget)
    
    context = {
        'form': form,
        'widget': widget,
    }
    
    return render(request, 'dashboard/widget_form.html', context)


@login_required
@require_POST
def widget_delete(request, pk):
    """Delete widget"""
    
    widget = get_object_or_404(Widget, pk=pk)
    dashboard_pk = widget.dashboard.pk
    
    log_dashboard_activity(widget.dashboard, request.user, 'widget_removed', f'Removed widget: {widget.name}')
    widget.delete()
    
    messages.success(request, 'Widget deleted successfully.')
    return redirect('dashboard:dashboard_detail', pk=dashboard_pk)


@login_required
def widget_data_api(request, pk):
    """Get widget data (AJAX)"""
    
    widget = get_object_or_404(Widget, pk=pk)
    
    # Check dashboard access
    if not widget.dashboard.can_user_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    data = get_widget_data(widget)
    
    return JsonResponse(data)


# ============================================================================
# USER PREFERENCES
# ============================================================================

@login_required
def preferences(request):
    """Manage user dashboard preferences"""
    
    preference, created = UserDashboardPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserDashboardPreferenceForm(request.POST, instance=preference, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully.')
            return redirect('dashboard:home')
    else:
        form = UserDashboardPreferenceForm(instance=preference, user=request.user)
    
    context = {
        'form': form,
        'preference': preference,
    }
    
    return render(request, 'dashboard/preferences.html', context)


# ============================================================================
# QUICK ACTIONS
# ============================================================================

@login_required
def quick_actions(request):
    """Display quick actions"""
    
    actions = QuickAction.objects.filter(is_active=True)
    
    # Filter by user access
    if not request.user.is_staff:
        actions = actions.filter(
            Q(is_public=True) |
            Q(allowed_users=request.user)
        )
    
    actions = actions.order_by('order')
    
    context = {
        'quick_actions': actions,
    }
    
    return render(request, 'dashboard/quick_actions.html', context)


# ============================================================================
# DASHBOARD TEMPLATES
# ============================================================================

@login_required
def create_from_template(request):
    """Create dashboard from template"""
    
    if request.method == 'POST':
        dashboard_type = request.POST.get('template_type')
        
        try:
            dashboard = create_dashboard_from_template(request.user, dashboard_type)
            messages.success(request, f'Dashboard "{dashboard.name}" created successfully.')
            return redirect('dashboard:dashboard_detail', pk=dashboard.pk)
        except ValueError as e:
            messages.error(request, str(e))
    
    templates = [
        {'type': 'executive', 'name': 'Executive Dashboard', 'description': 'High-level overview'},
        {'type': 'sales', 'name': 'Sales Dashboard', 'description': 'Sales performance'},
        {'type': 'finance', 'name': 'Finance Dashboard', 'description': 'Financial metrics'},
        {'type': 'operations', 'name': 'Operations Dashboard', 'description': 'Operations overview'},
    ]
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'dashboard/create_from_template.html', context)


@login_required
def widget_templates(request, dashboard_pk):
    """Display available widget templates"""
    
    dashboard = get_object_or_404(Dashboard, pk=dashboard_pk)
    templates = get_all_widget_templates()
    
    context = {
        'dashboard': dashboard,
        'templates': templates,
    }
    
    return render(request, 'dashboard/widget_templates.html', context)


@login_required
@require_POST
def add_widget_from_template(request, dashboard_pk):
    """Add widget from template"""
    
    dashboard = get_object_or_404(Dashboard, pk=dashboard_pk)
    template_name = request.POST.get('template_name')
    
    try:
        widget = create_widget_from_template(dashboard, template_name)
        log_dashboard_activity(dashboard, request.user, 'widget_added', f'Added widget from template: {widget.name}')
        messages.success(request, f'Widget "{widget.name}" added successfully.')
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('dashboard:dashboard_detail', pk=dashboard.pk)


# ============================================================================
# SHARING & COLLABORATION
# ============================================================================

@login_required
def share_dashboard(request, pk):
    """Share dashboard with users"""
    
    dashboard = get_object_or_404(Dashboard, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        form = ShareDashboardForm(request.POST)
        if form.is_valid():
            users = form.cleaned_data['users']
            make_public = form.cleaned_data['make_public']
            
            if make_public:
                dashboard.is_public = True
                dashboard.save()
            else:
                dashboard.shared_with.set(users)
            
            log_dashboard_activity(dashboard, request.user, 'shared')
            messages.success(request, 'Dashboard shared successfully.')
            return redirect('dashboard:dashboard_detail', pk=dashboard.pk)
    else:
        form = ShareDashboardForm()
    
    context = {
        'form': form,
        'dashboard': dashboard,
    }
    
    return render(request, 'dashboard/share_dashboard.html', context)


# ============================================================================
# SNAPSHOTS
# ============================================================================

@login_required
@require_POST
def create_snapshot(request, pk):
    """Create dashboard snapshot"""
    
    dashboard = get_object_or_404(Dashboard, pk=pk)
    
    # Export dashboard configuration
    snapshot_data = {
        'dashboard': {
            'name': dashboard.name,
            'layout': dashboard.layout,
            'columns': dashboard.columns,
        },
        'widgets': [
            {
                'name': w.name,
                'widget_type': w.widget_type,
                'data_source': w.data_source,
                'query_config': w.query_config,
            }
            for w in dashboard.widgets.all()
        ],
    }
    
    snapshot = DashboardSnapshot.objects.create(
        dashboard=dashboard,
        name=f"{dashboard.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        snapshot_data=snapshot_data,
        created_by=request.user
    )
    
    messages.success(request, 'Snapshot created successfully.')
    return redirect('dashboard:dashboard_detail', pk=dashboard.pk)


# ============================================================================
# ANALYTICS & STATS
# ============================================================================

@login_required
def analytics(request):
    """Dashboard analytics view"""
    
    context = {
        'overview': get_dashboard_overview_data(request.user),
        'financial': get_financial_summary(),
        'sales': get_sales_metrics(),
        'auctions': get_auction_metrics(),
    }
    
    return render(request, 'dashboard/analytics.html', context)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@login_required
def dashboard_data_api(request):
    """Get dashboard overview data (AJAX)"""
    
    data = get_dashboard_overview_data(request.user)
    return JsonResponse(data)


@login_required
def financial_data_api(request):
    """Get financial summary data (AJAX)"""
    
    days = int(request.GET.get('days', 30))
    data = get_financial_summary(days=days)
    return JsonResponse(data)


@login_required
def update_widget_position(request):
    """Update widget position (AJAX drag & drop)"""
    
    if request.method == 'POST':
        data = json.loads(request.body)
        widget_id = data.get('widget_id')
        position_x = data.get('position_x')
        position_y = data.get('position_y')
        
        widget = get_object_or_404(Widget, pk=widget_id)
        widget.position_x = position_x
        widget.position_y = position_y
        widget.save(update_fields=['position_x', 'position_y'])
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def set_default_dashboard(request, pk):
    """Set dashboard as default for user"""
    
    dashboard = get_object_or_404(Dashboard, pk=pk)
    
    if not dashboard.can_user_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    preference, created = UserDashboardPreference.objects.get_or_create(user=request.user)
    preference.default_dashboard = dashboard
    preference.save()
    
    messages.success(request, f'"{dashboard.name}" set as default dashboard.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('dashboard:home')


# ============================================================================
# EXPORT & IMPORT
# ============================================================================

@login_required
def export_dashboard(request, pk):
    """Export dashboard configuration"""
    
    dashboard = get_object_or_404(Dashboard, pk=pk)
    
    config = {
        'name': dashboard.name,
        'description': dashboard.description,
        'layout': dashboard.layout,
        'columns': dashboard.columns,
        'widgets': [
            {
                'name': w.name,
                'widget_type': w.widget_type,
                'chart_type': w.chart_type,
                'data_source': w.data_source,
                'query_config': w.query_config,
                'size': w.size,
                'order': w.order,
            }
            for w in dashboard.widgets.all()
        ],
    }
    
    response = HttpResponse(json.dumps(config, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{dashboard.name}.json"'
    
    return response