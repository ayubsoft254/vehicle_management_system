"""
Audit Views
Display and manage audit logs
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
import csv
from .models import AuditLog, LoginHistory
from apps.authentication.models import User
from utils.decorators import role_required, superuser_required
from utils.constants import UserRole, AuditAction


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def audit_list_view(request):
    """List all audit logs with search and filter"""
    logs = AuditLog.objects.all().select_related('user')
    
    # Search and filter
    search = request.GET.get('search', '')
    action = request.GET.get('action', '')
    model_name = request.GET.get('model', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if search:
        logs = logs.filter(
            Q(description__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    if action:
        logs = logs.filter(action=action)
    
    if model_name:
        logs = logs.filter(model_name=model_name)
    
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    # Statistics
    total_logs = logs.count()
    
    # Action breakdown
    action_stats = logs.values('action').annotate(count=Count('action')).order_by('-count')
    
    # Recent activity (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    recent_count = logs.filter(timestamp__gte=last_24h).count()
    
    # Get unique models
    models = AuditLog.objects.values_list('model_name', flat=True).distinct().order_by('model_name')
    
    # Get all users for filter
    users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_logs': total_logs,
        'action_stats': action_stats,
        'recent_count': recent_count,
        'models': models,
        'users': users,
        'search': search,
        'action': action,
        'model_name': model_name,
        'user_id': user_id,
        'date_from': date_from,
        'date_to': date_to,
        'action_choices': AuditAction.CHOICES,
    }
    return render(request, 'audit/audit_list.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def audit_detail_view(request, pk):
    """View detailed information about a specific audit log entry"""
    log = get_object_or_404(AuditLog, pk=pk)
    
    # Get related logs (same object)
    related_logs = []
    if log.model_name and log.object_id:
        related_logs = AuditLog.objects.filter(
            model_name=log.model_name,
            object_id=log.object_id
        ).exclude(pk=log.pk)[:10]
    
    context = {
        'log': log,
        'related_logs': related_logs,
    }
    return render(request, 'audit/audit_detail.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def user_activity_view(request, user_id):
    """View all activity for a specific user"""
    user_obj = get_object_or_404(User, pk=user_id)
    
    logs = AuditLog.objects.filter(user=user_obj)
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    action = request.GET.get('action', '')
    
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    if action:
        logs = logs.filter(action=action)
    
    # Statistics for this user
    total_actions = logs.count()
    action_breakdown = logs.values('action').annotate(count=Count('action')).order_by('-count')
    
    # Recent activity
    last_24h = timezone.now() - timedelta(hours=24)
    recent_actions = logs.filter(timestamp__gte=last_24h).count()
    
    # Most active days
    last_30_days = timezone.now() - timedelta(days=30)
    daily_activity = logs.filter(timestamp__gte=last_30_days).extra(
        select={'day': 'date(timestamp)'}
    ).values('day').annotate(count=Count('id')).order_by('-count')[:7]
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_obj': user_obj,
        'page_obj': page_obj,
        'total_actions': total_actions,
        'action_breakdown': action_breakdown,
        'recent_actions': recent_actions,
        'daily_activity': daily_activity,
        'date_from': date_from,
        'date_to': date_to,
        'action': action,
        'action_choices': AuditAction.CHOICES,
    }
    return render(request, 'audit/audit_user_activity.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def audit_export_view(request):
    """Export audit logs to CSV"""
    logs = AuditLog.objects.all().select_related('user')
    
    # Apply filters from GET parameters
    action = request.GET.get('action', '')
    model_name = request.GET.get('model', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if action:
        logs = logs.filter(action=action)
    if model_name:
        logs = logs.filter(model_name=model_name)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    # Limit to last 10,000 records for performance
    logs = logs[:10000]
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'User', 'Email', 'Action', 'Description',
        'Model', 'Object ID', 'IP Address', 'Request Path'
    ])
    
    for log in logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.get_full_name() if log.user else 'Anonymous',
            log.user.email if log.user else '',
            log.get_action_display(),
            log.description,
            log.model_name or '',
            log.object_id or '',
            log.ip_address or '',
            log.request_path or '',
        ])
    
    # Log the export action
    AuditLog.log_export(
        user=request.user,
        model_name='AuditLog',
        description=f'Exported {logs.count()} audit log entries',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def login_history_view(request):
    """View login history for all users"""
    history = LoginHistory.objects.all().select_related('user')
    
    # Filters
    success = request.GET.get('success', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if success == 'true':
        history = history.filter(success=True)
    elif success == 'false':
        history = history.filter(success=False)
    
    if user_id:
        history = history.filter(user_id=user_id)
    
    if date_from:
        history = history.filter(timestamp__gte=date_from)
    
    if date_to:
        history = history.filter(timestamp__lte=date_to)
    
    # Statistics
    total_attempts = history.count()
    successful_logins = history.filter(success=True).count()
    failed_logins = history.filter(success=False).count()
    
    # Recent suspicious activity
    suspicious = history.filter(success=False).values('ip_address').annotate(
        count=Count('id')
    ).filter(count__gte=3).order_by('-count')[:10]
    
    # Get all users for filter
    users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    # Pagination
    paginator = Paginator(history, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_attempts': total_attempts,
        'successful_logins': successful_logins,
        'failed_logins': failed_logins,
        'suspicious': suspicious,
        'users': users,
        'success': success,
        'user_id': user_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'audit/login_history.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def dashboard_stats_view(request):
    """Get audit statistics for dashboard (AJAX)"""
    days = int(request.GET.get('days', 7))
    since = timezone.now() - timedelta(days=days)
    
    logs = AuditLog.objects.filter(timestamp__gte=since)
    
    stats = {
        'total_actions': logs.count(),
        'unique_users': logs.values('user').distinct().count(),
        'by_action': list(logs.values('action').annotate(count=Count('action'))),
        'by_day': list(logs.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(count=Count('id')).order_by('day')),
        'top_users': list(logs.values(
            'user__first_name', 'user__last_name', 'user__email'
        ).annotate(count=Count('id')).order_by('-count')[:5]),
    }
    
    return JsonResponse(stats)


@login_required
@superuser_required
def audit_cleanup_view(request):
    """Delete old audit logs (admin only)"""
    if request.method == 'POST':
        days = int(request.POST.get('days', 90))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Count before deletion
        count = AuditLog.objects.filter(timestamp__lt=cutoff_date).count()
        
        # Delete old logs
        AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()
        
        # Log the cleanup
        AuditLog.objects.log_action(
            user=request.user,
            action=AuditAction.DELETE,
            description=f'Cleaned up {count} audit logs older than {days} days',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, f'{count} old audit logs have been deleted.')
        return redirect('audit:list')
    
    # Show cleanup form
    context = {
        'total_logs': AuditLog.objects.count(),
        'logs_30_days': AuditLog.objects.filter(
            timestamp__lt=timezone.now() - timedelta(days=30)
        ).count(),
        'logs_90_days': AuditLog.objects.filter(
            timestamp__lt=timezone.now() - timedelta(days=90)
        ).count(),
        'logs_180_days': AuditLog.objects.filter(
            timestamp__lt=timezone.now() - timedelta(days=180)
        ).count(),
    }
    return render(request, 'audit/cleanup_confirm.html', context)