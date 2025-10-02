"""
Reports App - Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Avg
from django.contrib import messages

from .models import (
    Report,
    ReportTemplate,
    ReportExecution,
    ReportWidget,
    SavedReport
)


class ReportExecutionInline(admin.TabularInline):
    model = ReportExecution
    extra = 0
    readonly_fields = ['status', 'triggered_by', 'started_at', 'completed_at', 'execution_time', 'row_count']
    fields = ['status', 'triggered_by', 'started_at', 'completed_at', 'execution_time', 'row_count']
    can_delete = False
    max_num = 5
    ordering = ['-created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


class ReportWidgetInline(admin.TabularInline):
    model = ReportWidget
    extra = 0
    fields = ['name', 'widget_type', 'chart_type', 'is_active', 'order']
    ordering = ['order']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'report_type_badge',
        'output_format',
        'is_scheduled',
        'frequency',
        'is_active',
        'execution_count',
        'last_execution_status_badge',
        'created_at',
    ]
    list_filter = [
        'report_type',
        'output_format',
        'is_scheduled',
        'frequency',
        'is_active',
        'last_execution_status',
        'created_at',
    ]
    search_fields = ['name', 'description']
    readonly_fields = [
        'id',
        'execution_count',
        'last_execution_status',
        'average_execution_time',
        'last_run',
        'created_at',
        'updated_at',
    ]
    filter_horizontal = ['recipients', 'allowed_users']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'report_type', 'template')
        }),
        ('Configuration', {
            'fields': (
                'query_config',
                'date_range_type',
                'custom_date_from',
                'custom_date_to'
            )
        }),
        ('Output Settings', {
            'fields': (
                'output_format',
                'include_charts',
                'include_summary',
                'include_details'
            )
        }),
        ('Scheduling', {
            'fields': (
                'is_scheduled',
                'frequency',
                'schedule_time',
                'schedule_day',
                'next_run',
                'last_run'
            )
        }),
        ('Recipients', {
            'fields': (
                'recipients',
                'email_recipients',
                'send_email'
            )
        }),
        ('Access Control', {
            'fields': (
                'created_by',
                'is_public',
                'allowed_users'
            )
        }),
        ('Status & Statistics', {
            'fields': (
                'is_active',
                'execution_count',
                'last_execution_status',
                'average_execution_time'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    inlines = [ReportWidgetInline, ReportExecutionInline]
    date_hierarchy = 'created_at'
    actions = [
        'activate_reports',
        'deactivate_reports',
        'run_reports',
        'schedule_reports',
        'unschedule_reports',
    ]
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('created_by', 'template')
        queryset = queryset.annotate(
            execution_total=Count('executions')
        )
        return queryset
    
    def report_type_badge(self, obj):
        colors = {
            'financial': 'green',
            'vehicle': 'blue',
            'client': 'purple',
            'auction': 'orange',
            'payment': 'teal',
        }
        color = colors.get(obj.report_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_report_type_display()
        )
    report_type_badge.short_description = 'Type'
    report_type_badge.admin_order_field = 'report_type'
    
    def last_execution_status_badge(self, obj):
        if not obj.last_execution_status:
            return format_html('<span style="color: gray;">-</span>')
        
        colors = {
            'completed': 'green',
            'failed': 'red',
            'in_progress': 'blue',
            'pending': 'orange',
        }
        color = colors.get(obj.last_execution_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.last_execution_status.title()
        )
    last_execution_status_badge.short_description = 'Last Status'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        
        # Calculate next run if scheduled
        if obj.is_scheduled and not obj.next_run:
            obj.next_run = obj.calculate_next_run()
        
        super().save_model(request, obj, form, change)
    
    def activate_reports(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} report(s) activated.', messages.SUCCESS)
    activate_reports.short_description = 'Activate selected reports'
    
    def deactivate_reports(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} report(s) deactivated.', messages.SUCCESS)
    deactivate_reports.short_description = 'Deactivate selected reports'
    
    def run_reports(self, request, queryset):
        count = 0
        for report in queryset:
            # Queue report execution (would be handled by task)
            count += 1
        self.message_user(request, f'{count} report(s) queued for execution.', messages.SUCCESS)
    run_reports.short_description = 'Run selected reports now'
    
    def schedule_reports(self, request, queryset):
        for report in queryset:
            report.is_scheduled = True
            report.next_run = report.calculate_next_run()
            report.save()
        self.message_user(request, f'{queryset.count()} report(s) scheduled.', messages.SUCCESS)
    schedule_reports.short_description = 'Schedule selected reports'
    
    def unschedule_reports(self, request, queryset):
        updated = queryset.update(is_scheduled=False, next_run=None)
        self.message_user(request, f'{updated} report(s) unscheduled.', messages.SUCCESS)
    unschedule_reports.short_description = 'Unschedule selected reports'


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'report_type',
        'layout',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'report_type',
        'layout',
        'is_active',
        'created_at',
    ]
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'report_type')
        }),
        ('Template Configuration', {
            'fields': (
                'layout',
                'columns',
                'grouping',
                'sorting',
                'aggregations'
            )
        }),
        ('Visual Settings', {
            'fields': (
                'header_template',
                'footer_template',
                'css_styles'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    actions = ['activate_templates', 'deactivate_templates', 'duplicate_template']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_templates(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} template(s) activated.', messages.SUCCESS)
    activate_templates.short_description = 'Activate selected templates'
    
    def deactivate_templates(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} template(s) deactivated.', messages.SUCCESS)
    deactivate_templates.short_description = 'Deactivate selected templates'
    
    def duplicate_template(self, request, queryset):
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copy)"
            template.save()
        self.message_user(request, f'{queryset.count()} template(s) duplicated.', messages.SUCCESS)
    duplicate_template.short_description = 'Duplicate selected templates'


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'report_link',
        'status_badge',
        'triggered_by_link',
        'is_scheduled',
        'started_at',
        'completed_at',
        'execution_time_display',
        'row_count',
        'output_format',
    ]
    list_filter = [
        'status',
        'output_format',
        'is_scheduled',
        'created_at',
    ]
    search_fields = [
        'report__name',
        'triggered_by__username',
        'error_message',
    ]
    readonly_fields = [
        'report',
        'status',
        'triggered_by',
        'is_scheduled',
        'started_at',
        'completed_at',
        'execution_time',
        'date_from',
        'date_to',
        'output_format',
        'file_path',
        'file_size',
        'result_data',
        'row_count',
        'error_message',
        'stack_trace',
        'created_at',
        'parameters',
    ]
    fieldsets = (
        ('Execution Details', {
            'fields': (
                'report',
                'status',
                'triggered_by',
                'is_scheduled'
            )
        }),
        ('Timing', {
            'fields': (
                'started_at',
                'completed_at',
                'execution_time'
            )
        }),
        ('Date Range', {
            'fields': ('date_from', 'date_to')
        }),
        ('Output', {
            'fields': (
                'output_format',
                'file_path',
                'file_size',
                'row_count'
            )
        }),
        ('Results', {
            'fields': ('result_data',),
            'classes': ('collapse',)
        }),
        ('Error Details', {
            'fields': ('error_message', 'stack_trace'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'parameters'),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['retry_failed_executions', 'delete_old_executions']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def report_link(self, obj):
        url = reverse('admin:reports_report_change', args=[obj.report.pk])
        return format_html('<a href="{}">{}</a>', url, obj.report.name)
    report_link.short_description = 'Report'
    
    def triggered_by_link(self, obj):
        if obj.triggered_by:
            url = reverse('admin:auth_user_change', args=[obj.triggered_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.triggered_by.get_full_name() or obj.triggered_by.username)
        return format_html('<span style="color: gray;">System</span>')
    triggered_by_link.short_description = 'Triggered By'
    
    def status_badge(self, obj):
        colors = {
            'completed': 'green',
            'failed': 'red',
            'in_progress': 'blue',
            'pending': 'orange',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def execution_time_display(self, obj):
        if obj.execution_time:
            return format_html('<span>{:.2f}s</span>', obj.execution_time)
        return '-'
    execution_time_display.short_description = 'Execution Time'
    execution_time_display.admin_order_field = 'execution_time'
    
    def retry_failed_executions(self, request, queryset):
        count = 0
        for execution in queryset.filter(status='failed'):
            # Queue retry (would be handled by task)
            count += 1
        self.message_user(request, f'{count} execution(s) queued for retry.', messages.SUCCESS)
    retry_failed_executions.short_description = 'Retry failed executions'
    
    def delete_old_executions(self, request, queryset):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=90)
        count = queryset.filter(created_at__lt=cutoff).delete()[0]
        self.message_user(request, f'{count} old execution(s) deleted.', messages.SUCCESS)
    delete_old_executions.short_description = 'Delete executions older than 90 days'


@admin.register(ReportWidget)
class ReportWidgetAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'widget_type',
        'chart_type',
        'data_source',
        'is_public',
        'is_active',
        'order',
        'created_at',
    ]
    list_filter = [
        'widget_type',
        'chart_type',
        'is_public',
        'is_active',
        'created_at',
    ]
    search_fields = ['name', 'description', 'data_source']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['allowed_users']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'widget_type', 'chart_type')
        }),
        ('Data Source', {
            'fields': (
                'report',
                'data_source',
                'query_config'
            )
        }),
        ('Display Settings', {
            'fields': (
                'refresh_interval',
                'width',
                'height',
                'order'
            )
        }),
        ('Access Control', {
            'fields': (
                'is_public',
                'allowed_users'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    list_editable = ['order', 'is_active']
    actions = ['activate_widgets', 'deactivate_widgets']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_widgets(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} widget(s) activated.', messages.SUCCESS)
    activate_widgets.short_description = 'Activate selected widgets'
    
    def deactivate_widgets(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} widget(s) deactivated.', messages.SUCCESS)
    deactivate_widgets.short_description = 'Deactivate selected widgets'


@admin.register(SavedReport)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'report_link',
        'custom_name',
        'access_count',
        'last_accessed',
        'created_at',
    ]
    list_filter = [
        'created_at',
        'last_accessed',
    ]
    search_fields = [
        'user__username',
        'report__name',
        'custom_name',
    ]
    readonly_fields = [
        'created_at',
        'last_accessed',
        'access_count',
    ]
    date_hierarchy = 'last_accessed'
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def report_link(self, obj):
        url = reverse('admin:reports_report_change', args=[obj.report.pk])
        return format_html('<a href="{}">{}</a>', url, obj.report.name)
    report_link.short_description = 'Report'