"""
Audit Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import AuditLog, LoginHistory
import json


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Audit Logs"""
    
    list_display = [
        'timestamp', 'user_display_name', 'action_badge', 
        'description_short', 'model_name', 'ip_address'
    ]
    
    list_filter = [
        'action', 'model_name', 'timestamp', 
        ('user', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'description', 'user__email', 'user__first_name', 
        'user__last_name', 'ip_address', 'model_name'
    ]
    
    readonly_fields = [
        'user', 'action', 'description', 'content_type', 
        'object_id', 'model_name', 'changes_display', 
        'ip_address', 'user_agent', 'request_path', 
        'request_method', 'additional_data_display', 'timestamp'
    ]
    
    fieldsets = (
        ('Action Information', {
            'fields': ('timestamp', 'user', 'action', 'description')
        }),
        ('Object Information', {
            'fields': ('content_type', 'object_id', 'model_name', 'changes_display'),
            'classes': ('collapse',)
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'request_path', 'request_method'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('additional_data_display',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50
    
    def user_display_name(self, obj):
        """Display user with email"""
        if obj.user:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.user.get_full_name(),
                obj.user.email
            )
        return format_html('<em style="color: #999;">Anonymous</em>')
    user_display_name.short_description = 'User'
    
    def action_badge(self, obj):
        """Display action as colored badge"""
        color_map = {
            'create': '#10b981',   # green
            'read': '#3b82f6',     # blue
            'update': '#f59e0b',   # yellow/orange
            'delete': '#ef4444',   # red
            'login': '#10b981',    # green
            'logout': '#6b7280',   # gray
            'export': '#8b5cf6',   # purple
        }
        color = color_map.get(obj.action, '#6b7280')
        icon = obj.get_action_icon()
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-block;">'
            '<i class="fas {} mr-1"></i> {}</span>',
            color,
            icon,
            obj.get_action_display().upper()
        )
    action_badge.short_description = 'Action'
    
    def description_short(self, obj):
        """Display shortened description"""
        if len(obj.description) > 80:
            return format_html(
                '<span title="{}">{}</span>',
                obj.description,
                obj.description[:80] + '...'
            )
        return obj.description
    description_short.short_description = 'Description'
    
    def changes_display(self, obj):
        """Display changes in formatted way"""
        if not obj.changes:
            return format_html('<em style="color: #999;">No changes recorded</em>')
        
        try:
            changes_html = '<table style="width: 100%; border-collapse: collapse;">'
            changes_html += '<tr style="background-color: #f3f4f6;"><th style="padding: 8px; text-align: left;">Field</th><th style="padding: 8px; text-align: left;">Old Value</th><th style="padding: 8px; text-align: left;">New Value</th></tr>'
            
            for field, values in obj.changes.items():
                if isinstance(values, dict) and 'old' in values and 'new' in values:
                    old_val = values['old'] if values['old'] not in [None, ''] else '<em>empty</em>'
                    new_val = values['new'] if values['new'] not in [None, ''] else '<em>empty</em>'
                    changes_html += f'<tr><td style="padding: 8px; border-top: 1px solid #e5e7eb;"><strong>{field}</strong></td><td style="padding: 8px; border-top: 1px solid #e5e7eb;">{old_val}</td><td style="padding: 8px; border-top: 1px solid #e5e7eb; color: #10b981;">{new_val}</td></tr>'
                else:
                    changes_html += f'<tr><td style="padding: 8px; border-top: 1px solid #e5e7eb;"><strong>{field}</strong></td><td colspan="2" style="padding: 8px; border-top: 1px solid #e5e7eb;">{values}</td></tr>'
            
            changes_html += '</table>'
            return mark_safe(changes_html)
        except:
            return format_html('<pre>{}</pre>', json.dumps(obj.changes, indent=2))
    changes_display.short_description = 'Changes'
    
    def additional_data_display(self, obj):
        """Display additional data in formatted way"""
        if not obj.additional_data:
            return format_html('<em style="color: #999;">No additional data</em>')
        
        try:
            return format_html(
                '<pre style="background-color: #f3f4f6; padding: 10px; border-radius: 4px; overflow: auto;">{}</pre>',
                json.dumps(obj.additional_data, indent=2)
            )
        except:
            return str(obj.additional_data)
    additional_data_display.short_description = 'Additional Data'
    
    def has_add_permission(self, request):
        """Don't allow manual creation of audit logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete audit logs"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Don't allow editing of audit logs"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist"""
        extra_context = extra_context or {}
        
        # Get action statistics
        action_stats = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        extra_context['action_stats'] = action_stats
        
        return super().changelist_view(request, extra_context)


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin interface for Login History"""
    
    list_display = [
        'timestamp', 'email_attempted', 'user_link', 
        'success_badge', 'ip_address', 'session_duration'
    ]
    
    list_filter = [
        'success', 'timestamp',
        ('user', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'email_attempted', 'user__email', 'user__first_name', 
        'user__last_name', 'ip_address'
    ]
    
    readonly_fields = [
        'user', 'email_attempted', 'success', 'failure_reason',
        'ip_address', 'user_agent', 'location', 'session_key',
        'logout_time', 'timestamp', 'session_duration'
    ]
    
    fieldsets = (
        ('Login Information', {
            'fields': ('timestamp', 'user', 'email_attempted', 'success', 'failure_reason')
        }),
        ('Session Information', {
            'fields': ('session_key', 'logout_time', 'session_duration')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'location'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50
    
    def user_link(self, obj):
        """Display user with link"""
        if obj.user:
            return format_html(
                '<a href="/admin/authentication/user/{}/change/">{}</a>',
                obj.user.pk,
                obj.user.get_full_name()
            )
        return format_html('<em style="color: #999;">Not found</em>')
    user_link.short_description = 'User'
    
    def success_badge(self, obj):
        """Display success status as badge"""
        if obj.success:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">'
                '<i class="fas fa-check-circle"></i> SUCCESS</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">'
                '<i class="fas fa-times-circle"></i> FAILED</span>'
            )
    success_badge.short_description = 'Status'
    
    def session_duration(self, obj):
        """Display session duration"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return format_html('<em style="color: #999;">Active</em>')
    session_duration.short_description = 'Duration'
    
    def has_add_permission(self, request):
        """Don't allow manual creation of login history"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete login history"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Don't allow editing of login history"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist"""
        extra_context = extra_context or {}
        
        # Get login statistics
        total_attempts = LoginHistory.objects.count()
        successful = LoginHistory.objects.filter(success=True).count()
        failed = LoginHistory.objects.filter(success=False).count()
        
        # Suspicious IPs (3+ failed attempts)
        suspicious_ips = LoginHistory.objects.filter(
            success=False
        ).values('ip_address').annotate(
            count=Count('id')
        ).filter(count__gte=3).order_by('-count')[:10]
        
        extra_context['total_attempts'] = total_attempts
        extra_context['successful'] = successful
        extra_context['failed'] = failed
        extra_context['suspicious_ips'] = suspicious_ips
        
        return super().changelist_view(request, extra_context)


# Customize admin site header
admin.site.site_header = "Vehicle Sales Management System - Administration"
admin.site.site_title = "VSMS Admin"
admin.site.index_title = "System Administration"