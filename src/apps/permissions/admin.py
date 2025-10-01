"""
Permissions Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import RolePermission, PermissionHistory


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Admin interface for Role Permissions"""
    
    list_display = [
        'role_badge', 'module_badge', 'access_level_badge',
        'can_create', 'can_edit', 'can_delete', 'can_export',
        'is_active', 'updated_at'
    ]
    
    list_filter = [
        'role', 'module_name', 'access_level',
        'is_active', 'can_create', 'can_edit', 'can_delete'
    ]
    
    search_fields = ['role', 'module_name', 'description']
    
    list_editable = ['is_active']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('role', 'module_name', 'access_level', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_create', 'can_edit', 'can_delete', 'can_export')
        }),
        ('Additional Information', {
            'fields': ('description', 'created_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    ordering = ['role', 'module_name']
    
    def role_badge(self, obj):
        """Display role as colored badge"""
        color_map = {
            'admin': '#ef4444',
            'manager': '#8b5cf6',
            'accountant': '#10b981',
            'sales': '#3b82f6',
            'auctioneer': '#f59e0b',
            'clerk': '#6b7280',
        }
        color = color_map.get(obj.role, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_role_display().upper()
        )
    role_badge.short_description = 'Role'
    
    def module_badge(self, obj):
        """Display module as badge"""
        return format_html(
            '<span style="background-color: #e5e7eb; color: #1f2937; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            obj.get_module_name_display()
        )
    module_badge.short_description = 'Module'
    
    def access_level_badge(self, obj):
        """Display access level as colored badge"""
        color_map = {
            'no_access': '#ef4444',
            'read_only': '#f59e0b',
            'read_write': '#3b82f6',
            'full_access': '#10b981',
        }
        color = color_map.get(obj.access_level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_access_level_display().upper()
        )
    access_level_badge.short_description = 'Access Level'
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the permission"""
        if not change:  # Creating new
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
        # Log the change in history
        action = 'updated' if change else 'created'
        PermissionHistory.objects.create(
            permission=obj,
            changed_by=request.user,
            action=action,
            new_value={
                'access_level': obj.access_level,
                'can_create': obj.can_create,
                'can_edit': obj.can_edit,
                'can_delete': obj.can_delete,
                'can_export': obj.can_export,
            }
        )
    
    actions = ['activate_permissions', 'deactivate_permissions', 'reset_to_read_only']
    
    def activate_permissions(self, request, queryset):
        """Activate selected permissions"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} permission(s) activated.')
    activate_permissions.short_description = 'Activate selected permissions'
    
    def deactivate_permissions(self, request, queryset):
        """Deactivate selected permissions"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} permission(s) deactivated.')
    deactivate_permissions.short_description = 'Deactivate selected permissions'
    
    def reset_to_read_only(self, request, queryset):
        """Reset selected permissions to read-only"""
        count = queryset.update(
            access_level='read_only',
            can_create=False,
            can_edit=False,
            can_delete=False
        )
        self.message_user(request, f'{count} permission(s) reset to read-only.')
    reset_to_read_only.short_description = 'Reset to read-only access'


@admin.register(PermissionHistory)
class PermissionHistoryAdmin(admin.ModelAdmin):
    """Admin interface for Permission History"""
    
    list_display = [
        'permission', 'action_badge', 'changed_by',
        'timestamp'
    ]
    
    list_filter = ['action', 'timestamp']
    
    search_fields = [
        'permission__role',
        'permission__module_name',
        'changed_by__email',
        'reason'
    ]
    
    readonly_fields = [
        'permission', 'changed_by', 'action',
        'old_value', 'new_value', 'timestamp'
    ]
    
    fieldsets = (
        ('Change Information', {
            'fields': ('permission', 'changed_by', 'action', 'timestamp')
        }),
        ('Details', {
            'fields': ('old_value', 'new_value', 'reason')
        }),
    )
    
    ordering = ['-timestamp']
    
    def action_badge(self, obj):
        """Display action as colored badge"""
        color_map = {
            'created': '#10b981',
            'updated': '#3b82f6',
            'deleted': '#ef4444',
            'activated': '#10b981',
            'deactivated': '#f59e0b',
        }
        color = color_map.get(obj.action, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.action.upper()
        )
    action_badge.short_description = 'Action'
    
    def has_add_permission(self, request):
        """Don't allow manual creation of history"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of history"""
        return False