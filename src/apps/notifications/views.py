"""
Notifications App - Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from datetime import timedelta
import json

from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    NotificationSchedule,
    NotificationLog
)
from .forms import (
    NotificationForm,
    BulkNotificationForm,
    NotificationFilterForm,
    NotificationPreferenceForm,
    QuickPreferenceForm,
    NotificationTemplateForm,
    NotificationScheduleForm,
    NotificationSearchForm,
    NotificationActionForm
)


# ============================================================================
# NOTIFICATION LIST & DETAIL VIEWS
# ============================================================================

@login_required
def notification_list(request):
    """Display user's notifications"""
    
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply filters
    filter_form = NotificationFilterForm(request.GET)
    if filter_form.is_valid():
        notification_type = filter_form.cleaned_data.get('notification_type')
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        priority = filter_form.cleaned_data.get('priority')
        if priority:
            notifications = notifications.filter(priority=priority)
        
        is_read = filter_form.cleaned_data.get('is_read')
        if is_read == 'true':
            notifications = notifications.filter(is_read=True)
        elif is_read == 'false':
            notifications = notifications.filter(is_read=False)
        
        date_from = filter_form.cleaned_data.get('date_from')
        if date_from:
            notifications = notifications.filter(created_at__gte=date_from)
        
        date_to = filter_form.cleaned_data.get('date_to')
        if date_to:
            notifications = notifications.filter(created_at__lte=date_to)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'notifications': page_obj,
        'filter_form': filter_form,
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
        'total_count': Notification.objects.filter(user=request.user).count(),
    }
    
    return render(request, 'notifications/notification_list.html', context)


@login_required
def notification_detail(request, pk):
    """View notification details"""
    
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    # Mark as read
    if not notification.is_read:
        notification.mark_as_read()
    
    context = {
        'notification': notification,
    }
    
    return render(request, 'notifications/notification_detail.html', context)


@login_required
def unread_notifications(request):
    """Display only unread notifications"""
    
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'notifications': page_obj,
        'unread_count': notifications.count(),
    }
    
    return render(request, 'notifications/unread_notifications.html', context)


# ============================================================================
# NOTIFICATION ACTIONS
# ============================================================================

@login_required
@require_POST
def mark_as_read(request, pk):
    """Mark single notification as read"""
    
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Marked as read'})
    
    messages.success(request, 'Notification marked as read.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def mark_as_unread(request, pk):
    """Mark single notification as unread"""
    
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_unread()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Marked as unread'})
    
    messages.success(request, 'Notification marked as unread.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def mark_all_as_read(request):
    """Mark all notifications as read"""
    
    count = Notification.objects.mark_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'count': count})
    
    messages.success(request, f'{count} notification(s) marked as read.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def dismiss_notification(request, pk):
    """Dismiss notification"""
    
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.dismiss()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Notification dismissed.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def delete_notification(request, pk):
    """Delete notification"""
    
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Notification deleted.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def batch_action(request):
    """Perform batch actions on notifications"""
    
    form = NotificationActionForm(request.POST)
    
    if form.is_valid():
        action = form.cleaned_data['action']
        notification_ids = form.cleaned_data['notification_ids']
        
        notifications = Notification.objects.filter(
            pk__in=notification_ids,
            user=request.user
        )
        
        count = 0
        if action == 'mark_read':
            for notification in notifications:
                notification.mark_as_read()
                count += 1
            messages.success(request, f'{count} notification(s) marked as read.')
        
        elif action == 'mark_unread':
            for notification in notifications:
                notification.mark_as_unread()
                count += 1
            messages.success(request, f'{count} notification(s) marked as unread.')
        
        elif action == 'dismiss':
            for notification in notifications:
                notification.dismiss()
                count += 1
            messages.success(request, f'{count} notification(s) dismissed.')
        
        elif action == 'delete':
            count = notifications.delete()[0]
            messages.success(request, f'{count} notification(s) deleted.')
    
    return redirect('notifications:notification_list')


# ============================================================================
# NOTIFICATION PREFERENCES
# ============================================================================

@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    
    preference, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification preferences updated successfully.')
            return redirect('notifications:preferences')
    else:
        form = NotificationPreferenceForm(instance=preference)
    
    context = {
        'form': form,
        'preference': preference,
    }
    
    return render(request, 'notifications/preferences.html', context)


@login_required
@require_POST
def toggle_notifications(request):
    """Quick toggle notifications on/off"""
    
    preference, created = NotificationPreference.objects.get_or_create(user=request.user)
    preference.enabled = not preference.enabled
    preference.save()
    
    status = 'enabled' if preference.enabled else 'disabled'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'enabled': preference.enabled})
    
    messages.success(request, f'Notifications {status}.')
    return redirect('notifications:preferences')


# ============================================================================
# NOTIFICATION CREATION (ADMIN)
# ============================================================================

@login_required
@permission_required('notifications.add_notification')
def create_notification(request):
    """Create manual notification"""
    
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            notification = form.save()
            messages.success(request, 'Notification created successfully.')
            return redirect('notifications:notification_list')
    else:
        form = NotificationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'notifications/create_notification.html', context)


@login_required
@permission_required('notifications.add_notification')
def bulk_notification(request):
    """Send notification to multiple users"""
    
    if request.method == 'POST':
        form = BulkNotificationForm(request.POST)
        if form.is_valid():
            users = form.cleaned_data['users']
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            notification_type = form.cleaned_data['notification_type']
            priority = form.cleaned_data['priority']
            send_email = form.cleaned_data['send_email']
            send_sms = form.cleaned_data['send_sms']
            
            delivery_methods = ['in_app']
            if send_email:
                delivery_methods.append('email')
            if send_sms:
                delivery_methods.append('sms')
            
            count = 0
            for user in users:
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    delivery_methods=delivery_methods
                )
                count += 1
            
            messages.success(request, f'Notification sent to {count} user(s).')
            return redirect('notifications:notification_list')
    else:
        form = BulkNotificationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'notifications/bulk_notification.html', context)


# ============================================================================
# NOTIFICATION TEMPLATES
# ============================================================================

class NotificationTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = NotificationTemplate
    template_name = 'notifications/template_list.html'
    context_object_name = 'templates'
    permission_required = 'notifications.view_notificationtemplate'
    paginate_by = 20


class NotificationTemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    permission_required = 'notifications.add_notificationtemplate'
    success_url = reverse_lazy('notifications:template_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Template created successfully.')
        return super().form_valid(form)


class NotificationTemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    permission_required = 'notifications.change_notificationtemplate'
    success_url = reverse_lazy('notifications:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Template updated successfully.')
        return super().form_valid(form)


class NotificationTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = NotificationTemplate
    template_name = 'notifications/template_confirm_delete.html'
    permission_required = 'notifications.delete_notificationtemplate'
    success_url = reverse_lazy('notifications:template_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Template deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# NOTIFICATION SCHEDULES
# ============================================================================

class NotificationScheduleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = NotificationSchedule
    template_name = 'notifications/schedule_list.html'
    context_object_name = 'schedules'
    permission_required = 'notifications.view_notificationschedule'
    paginate_by = 20


class NotificationScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = NotificationSchedule
    form_class = NotificationScheduleForm
    template_name = 'notifications/schedule_form.html'
    permission_required = 'notifications.add_notificationschedule'
    success_url = reverse_lazy('notifications:schedule_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.next_run = form.instance.scheduled_time
        messages.success(self.request, 'Schedule created successfully.')
        return super().form_valid(form)


class NotificationScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = NotificationSchedule
    form_class = NotificationScheduleForm
    template_name = 'notifications/schedule_form.html'
    permission_required = 'notifications.change_notificationschedule'
    success_url = reverse_lazy('notifications:schedule_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Schedule updated successfully.')
        return super().form_valid(form)


class NotificationScheduleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = NotificationSchedule
    template_name = 'notifications/schedule_confirm_delete.html'
    permission_required = 'notifications.delete_notificationschedule'
    success_url = reverse_lazy('notifications:schedule_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Schedule deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# API ENDPOINTS (JSON)
# ============================================================================

@login_required
def notification_count_api(request):
    """Get notification counts"""
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    total_count = Notification.objects.filter(user=request.user).count()
    
    data = {
        'unread_count': unread_count,
        'total_count': total_count,
    }
    
    return JsonResponse(data)


@login_required
def recent_notifications_api(request):
    """Get recent notifications (AJAX)"""
    
    limit = int(request.GET.get('limit', 10))
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:limit]
    
    data = [{
        'id': str(notification.id),
        'title': notification.title,
        'message': notification.message,
        'notification_type': notification.notification_type,
        'priority': notification.priority,
        'is_read': notification.is_read,
        'created_at': notification.created_at.isoformat(),
        'action_url': notification.action_url,
    } for notification in notifications]
    
    return JsonResponse({'notifications': data})


@login_required
def notification_stats_api(request):
    """Get notification statistics"""
    
    user_notifications = Notification.objects.filter(user=request.user)
    
    stats = {
        'total': user_notifications.count(),
        'unread': user_notifications.filter(is_read=False).count(),
        'by_type': {},
        'by_priority': {},
        'recent': user_notifications.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    # By type
    by_type = user_notifications.values('notification_type').annotate(count=Count('id'))
    for item in by_type:
        stats['by_type'][item['notification_type']] = item['count']
    
    # By priority
    by_priority = user_notifications.values('priority').annotate(count=Count('id'))
    for item in by_priority:
        stats['by_priority'][item['priority']] = item['count']
    
    return JsonResponse(stats)


# ============================================================================
# DASHBOARD & ANALYTICS
# ============================================================================

@login_required
def notification_dashboard(request):
    """Notification dashboard with stats"""
    
    user_notifications = Notification.objects.filter(user=request.user)
    
    context = {
        'unread_count': user_notifications.filter(is_read=False).count(),
        'total_count': user_notifications.count(),
        'urgent_count': user_notifications.filter(priority='urgent', is_read=False).count(),
        'recent_notifications': user_notifications.order_by('-created_at')[:5],
        'by_type': user_notifications.values('notification_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5],
        'by_priority': user_notifications.values('priority').annotate(
            count=Count('id')
        ).order_by('-count'),
    }
    
    return render(request, 'notifications/dashboard.html', context)


@login_required
@permission_required('notifications.view_notificationlog')
def notification_logs(request):
    """View notification delivery logs"""
    
    logs = NotificationLog.objects.select_related('notification').order_by('-created_at')
    
    # Filter by delivery method
    method = request.GET.get('method')
    if method:
        logs = logs.filter(delivery_method=method)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        logs = logs.filter(status=status)
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
    }
    
    return render(request, 'notifications/logs.html', context)


# ============================================================================
# UTILITY VIEWS
# ============================================================================

@login_required
def clear_all_notifications(request):
    """Clear all read notifications"""
    
    if request.method == 'POST':
        count = Notification.objects.filter(user=request.user, is_read=True).delete()[0]
        messages.success(request, f'{count} notification(s) cleared.')
        return redirect('notifications:notification_list')
    
    return render(request, 'notifications/clear_confirm.html')


@login_required
def export_notifications(request):
    """Export notifications to CSV"""
    
    import csv
    from io import StringIO
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow(['Date', 'Title', 'Message', 'Type', 'Priority', 'Read', 'Sent'])
    
    # Data
    for notification in notifications:
        writer.writerow([
            notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            notification.title,
            notification.message,
            notification.get_notification_type_display(),
            notification.get_priority_display(),
            'Yes' if notification.is_read else 'No',
            'Yes' if notification.is_sent else 'No',
        ])
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="notifications.csv"'
    
    return response