from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AuditLog, LoginAttempt, UserSession, SystemEvent, DataExport, ComplianceReport

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'action_type', 'module_name', 
        'severity', 'is_successful', 'ip_address'
    ]
    list_filter = [
        'action_type', 'module_name', 'severity', 'is_successful',
        'is_sensitive', 'timestamp'
    ]
    search_fields = ['user__username', 'description', 'ip_address', 'module_name']
    readonly_fields = [
        'user', 'action_type', 'description', 'severity', 'content_type',
        'object_id', 'module_name', 'table_name', 'record_id', 'ip_address',
        'user_agent', 'request_method', 'request_url', 'old_values',
        'new_values', 'changed_fields', 'timestamp', 'session_key',
        'is_successful', 'error_message', 'is_sensitive'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete audit logs
        return request.user.is_superuser
    
    def get_queryset(self, queryset):
        return super().get_queryset(queryset).select_related('user', 'content_type')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('timestamp', 'user', 'action_type', 'module_name', 'severity')
        }),
        ('Action Details', {
            'fields': ('description', 'is_successful', 'error_message', 'is_sensitive')
        }),
        ('Object Information', {
            'fields': ('content_type', 'object_id', 'table_name', 'record_id'),
            'classes': ('collapse',)
        }),
        ('Request Information', {
            'fields': ('request_method', 'request_url', 'ip_address', 'user_agent', 'session_key'),
            'classes': ('collapse',)
        }),
        ('Data Changes', {
            'fields': ('old_values', 'new_values', 'changed_fields'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'username', 'is_successful', 'ip_address', 'failure_reason']
    list_filter = ['is_successful', 'timestamp']
    search_fields = ['username', 'ip_address']
    readonly_fields = ['username', 'ip_address', 'user_agent', 'is_successful', 'failure_reason', 'timestamp', 'user']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_time', 'last_activity', 'is_active', 'ip_address']
    list_filter = ['is_active', 'login_time']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['user', 'session_key', 'ip_address', 'user_agent', 'login_time', 'last_activity', 'logout_time']
    date_hierarchy = 'login_time'
    ordering = ['-login_time']
    
    def has_add_permission(self, request):
        return False


@admin.register(SystemEvent)
class SystemEventAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'event_type', 'severity', 'resolved', 'resolved_by']
    list_filter = ['event_type', 'severity', 'resolved', 'timestamp']
    search_fields = ['description']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_type', 'description', 'severity', 'timestamp')
        }),
        ('Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_by', 'resolved_at')
        }),
    )


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'export_type', 'module_name', 'file_name', 'formatted_file_size']
    list_filter = ['export_type', 'module_name', 'timestamp']
    search_fields = ['user__username', 'description', 'file_name']
    readonly_fields = ['user', 'export_type', 'module_name', 'description', 'file_name', 'file_size', 'record_count', 'filters_applied', 'timestamp', 'ip_address']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'start_date', 'end_date', 'generated_by', 'generated_at']
    list_filter = ['report_type', 'generated_at']
    search_fields = ['title', 'description']
    date_hierarchy = 'generated_at'
    ordering = ['-generated_at']