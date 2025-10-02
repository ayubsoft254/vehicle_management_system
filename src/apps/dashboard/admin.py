"""
Dashboard App - Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count
from django.contrib import messages

from .models import (
    Dashboard,
    Widget,
    UserDashboardPreference,
    DashboardActivity,
    QuickAction,
    DashboardSnapshot,
    MetricCache
)


class WidgetInline(admin.TabularInline):
    model = Widget
    extra = 0
    fields = ['name', 'widget_type', 'size', 'order', 'is_active']
    ordering = ['order']


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'created_by_link',
        'layout',
        'widget_count',
        'is_public',
        'is_default',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'layout',
        'is_public',
        'is_default',
        'is_active',
        'theme',
        'created_at',
    ]
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['shared_with']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'created_by')
        }),
        ('Layout Configuration', {
            'fields': ('layout', 'columns', 'theme')
        }),
        ('Access Control', {
            'fields': ('is_public', 'is_default', 'shared_with')
        }),
        ('Settings', {
            'fields': ('auto_refresh', 'refresh_interval')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    inlines = [WidgetInline]
    actions = [
        'make_public',
        'make_private',
        'set_as_default',
        'duplicate_dashboard',
        'activate_dashboards',
        'deactivate_dashboards',
    ]
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('created_by')
        queryset = queryset.annotate(widgets_count=Count('widgets'))
        return queryset
    
    def created_by_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.created_by.pk])
        return format_html('<a href="{}">{}</a>', url, obj.created_by.get_full_name() or obj.created_by.username)
    created_by_link.short_description = 'Created By'
    
    def widget_count(self, obj):
        return obj.widgets.filter(is_active=True).count()
    widget_count.short_description = 'Widgets'
    widget_count.admin_order_field = 'widgets_count'
    
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} dashboard(s) made public.', messages.SUCCESS)
    make_public.short_description = 'Make selected dashboards public'
    
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} dashboard(s) made private.', messages.SUCCESS)
    make_private.short_description = 'Make selected dashboards private'
    
    def set_as_default(self, request, queryset):
        # First, unset all defaults
        Dashboard.objects.filter(is_default=True).update(is_default=False)
        # Set selected as default
        updated = queryset.update(is_default=True)
        self.message_user(request, f'{updated} dashboard(s) set as default.', messages.SUCCESS)
    set_as_default.short_description = 'Set as default dashboard'
    
    def duplicate_dashboard(self, request, queryset):
        for dashboard in queryset:
            # Create copy
            new_dashboard = Dashboard.objects.create(
                name=f"{dashboard.name} (Copy)",
                description=dashboard.description,
                layout=dashboard.layout,
                columns=dashboard.columns,
                created_by=request.user,
                is_public=False,
                theme=dashboard.theme,
            )
            # Copy widgets
            for widget in dashboard.widgets.all():
                Widget.objects.create(
                    dashboard=new_dashboard,
                    name=widget.name,
                    widget_type=widget.widget_type,
                    data_source=widget.data_source,
                    query_config=widget.query_config,
                    width=widget.width,
                    height=widget.height,
                    order=widget.order,
                )
        self.message_user(request, f'{queryset.count()} dashboard(s) duplicated.', messages.SUCCESS)
    duplicate_dashboard.short_description = 'Duplicate selected dashboards'
    
    def activate_dashboards(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} dashboard(s) activated.', messages.SUCCESS)
    activate_dashboards.short_description = 'Activate selected dashboards'
    
    def deactivate_dashboards(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} dashboard(s) deactivated.', messages.SUCCESS)
    deactivate_dashboards.short_description = 'Deactivate selected dashboards'


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'dashboard_link',
        'widget_type_badge',
        'size',
        'order',
        'is_active',
        'auto_refresh',
        'updated_at',
    ]
    list_filter = [
        'widget_type',
        'chart_type',
        'size',
        'is_active',
        'auto_refresh',
        'created_at',
    ]
    search_fields = ['name', 'description', 'dashboard__name', 'data_source']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('dashboard', 'name', 'description')
        }),
        ('Widget Type', {
            'fields': ('widget_type', 'chart_type')
        }),
        ('Data Source', {
            'fields': ('data_source', 'query_config')
        }),
        ('Layout', {
            'fields': ('position_x', 'position_y', 'width', 'height', 'size', 'order')
        }),
        ('Display Settings', {
            'fields': (
                'show_title',
                'show_border',
                'title_color',
                'background_color'
            )
        }),
        ('Refresh Settings', {
            'fields': ('auto_refresh', 'refresh_interval')
        }),
        ('Custom Configuration', {
            'fields': ('custom_css', 'custom_config'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    list_editable = ['order', 'is_active']
    actions = ['activate_widgets', 'deactivate_widgets', 'reset_positions']
    
    def dashboard_link(self, obj):
        url = reverse('admin:dashboard_dashboard_change', args=[obj.dashboard.pk])
        return format_html('<a href="{}">{}</a>', url, obj.dashboard.name)
    dashboard_link.short_description = 'Dashboard'
    
    def widget_type_badge(self, obj):
        colors = {
            'metric': 'blue',
            'chart': 'green',
            'table': 'purple',
            'list': 'orange',
            'calendar': 'teal',
        }
        color = colors.get(obj.widget_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_widget_type_display()
        )
    widget_type_badge.short_description = 'Type'
    
    def activate_widgets(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} widget(s) activated.', messages.SUCCESS)
    activate_widgets.short_description = 'Activate selected widgets'
    
    def deactivate_widgets(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} widget(s) deactivated.', messages.SUCCESS)
    deactivate_widgets.short_description = 'Deactivate selected widgets'
    
    def reset_positions(self, request, queryset):
        for widget in queryset:
            widget.position_x = 0
            widget.position_y = 0
            widget.save(update_fields=['position_x', 'position_y'])
        self.message_user(request, f'{queryset.count()} widget(s) positions reset.', messages.SUCCESS)
    reset_positions.short_description = 'Reset widget positions'


@admin.register(UserDashboardPreference)
class UserDashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'default_dashboard_link',
        'theme',
        'compact_mode',
        'show_notifications',
        'updated_at',
    ]
    list_filter = [
        'theme',
        'compact_mode',
        'show_notifications',
        'enable_animations',
        'updated_at',
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('User', {
            'fields': ('user', 'default_dashboard')
        }),
        ('Display Preferences', {
            'fields': ('theme', 'compact_mode', 'show_grid_lines')
        }),
        ('Widget Preferences', {
            'fields': ('default_refresh_interval', 'enable_animations')
        }),
        ('Notification Preferences', {
            'fields': (
                'show_notifications',
                'show_quick_actions',
                'show_activity_feed'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def default_dashboard_link(self, obj):
        if obj.default_dashboard:
            url = reverse('admin:dashboard_dashboard_change', args=[obj.default_dashboard.pk])
            return format_html('<a href="{}">{}</a>', url, obj.default_dashboard.name)
        return '-'
    default_dashboard_link.short_description = 'Default Dashboard'


@admin.register(DashboardActivity)
class DashboardActivityAdmin(admin.ModelAdmin):
    list_display = [
        'dashboard_link',
        'user_link',
        'activity_type_badge',
        'description_short',
        'created_at',
    ]
    list_filter = [
        'activity_type',
        'created_at',
    ]
    search_fields = [
        'dashboard__name',
        'user__username',
        'description',
    ]
    readonly_fields = ['dashboard', 'user', 'activity_type', 'description', 'metadata', 'created_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def dashboard_link(self, obj):
        url = reverse('admin:dashboard_dashboard_change', args=[obj.dashboard.pk])
        return format_html('<a href="{}">{}</a>', url, obj.dashboard.name)
    dashboard_link.short_description = 'Dashboard'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
        return 'System'
    user_link.short_description = 'User'
    
    def activity_type_badge(self, obj):
        colors = {
            'view': 'blue',
            'widget_added': 'green',
            'widget_removed': 'red',
            'widget_updated': 'orange',
            'layout_changed': 'purple',
        }
        color = colors.get(obj.activity_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_activity_type_display()
        )
    activity_type_badge.short_description = 'Activity'
    
    def description_short(self, obj):
        if len(obj.description) > 50:
            return f"{obj.description[:47]}..."
        return obj.description
    description_short.short_description = 'Description'


@admin.register(QuickAction)
class QuickActionAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'action_type',
        'icon_display',
        'order',
        'is_public',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'action_type',
        'icon',
        'is_public',
        'is_active',
        'created_at',
    ]
    search_fields = ['name', 'description', 'action_url']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['allowed_users']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Action Configuration', {
            'fields': ('action_type', 'action_url', 'action_config')
        }),
        ('Display', {
            'fields': ('icon', 'color', 'order')
        }),
        ('Access Control', {
            'fields': ('is_public', 'allowed_users')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    list_editable = ['order', 'is_active']
    actions = ['activate_actions', 'deactivate_actions', 'make_public_actions']
    
    def icon_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            obj.color,
            obj.icon.upper()
        )
    icon_display.short_description = 'Icon'
    
    def activate_actions(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} action(s) activated.', messages.SUCCESS)
    activate_actions.short_description = 'Activate selected actions'
    
    def deactivate_actions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} action(s) deactivated.', messages.SUCCESS)
    deactivate_actions.short_description = 'Deactivate selected actions'
    
    def make_public_actions(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} action(s) made public.', messages.SUCCESS)
    make_public_actions.short_description = 'Make selected actions public'


@admin.register(DashboardSnapshot)
class DashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'dashboard_link',
        'created_by_link',
        'created_at',
    ]
    list_filter = ['created_at']
    search_fields = ['name', 'description', 'dashboard__name']
    readonly_fields = ['created_at', 'snapshot_data']
    fieldsets = (
        ('Basic Information', {
            'fields': ('dashboard', 'name', 'description')
        }),
        ('Snapshot Data', {
            'fields': ('snapshot_data',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        })
    )
    date_hierarchy = 'created_at'
    
    def dashboard_link(self, obj):
        url = reverse('admin:dashboard_dashboard_change', args=[obj.dashboard.pk])
        return format_html('<a href="{}">{}</a>', url, obj.dashboard.name)
    dashboard_link.short_description = 'Dashboard'
    
    def created_by_link(self, obj):
        if obj.created_by:
            url = reverse('admin:auth_user_change', args=[obj.created_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.created_by.get_full_name() or obj.created_by.username)
        return '-'
    created_by_link.short_description = 'Created By'


@admin.register(MetricCache)
class MetricCacheAdmin(admin.ModelAdmin):
    list_display = [
        'metric_name',
        'metric_key',
        'is_expired_display',
        'updated_at',
        'expires_at',
    ]
    list_filter = ['updated_at', 'expires_at']
    search_fields = ['metric_key', 'metric_name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_key', 'metric_name')
        }),
        ('Cached Data', {
            'fields': ('value',)
        }),
        ('Cache Management', {
            'fields': ('created_at', 'updated_at', 'expires_at')
        })
    )
    actions = ['clear_expired_cache', 'clear_all_cache']
    
    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">✗ Expired</span>')
        return format_html('<span style="color: green;">✓ Valid</span>')
    is_expired_display.short_description = 'Status'
    
    def clear_expired_cache(self, request, queryset):
        count = queryset.filter(expires_at__lt=timezone.now()).delete()[0]
        self.message_user(request, f'{count} expired cache(s) cleared.', messages.SUCCESS)
    clear_expired_cache.short_description = 'Clear expired caches'
    
    def clear_all_cache(self, request, queryset):
        count = queryset.delete()[0]
        self.message_user(request, f'{count} cache(s) cleared.', messages.SUCCESS)
    clear_all_cache.short_description = 'Clear all selected caches'