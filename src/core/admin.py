from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, RolePermission, SystemSettings, Client, Domain


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin for Tenant/Client management.
    """
    list_display = ['name', 'company_name', 'company_email', 'is_active', 'created_on']
    list_filter = ['is_active', 'created_on']
    search_fields = ['name', 'company_name', 'company_email']
    readonly_fields = ['created_on', 'schema_name']
    
    fieldsets = (
        ('Tenant Information', {
            'fields': ('name', 'schema_name', 'created_on')
        }),
        ('Company Details', {
            'fields': ('company_name', 'company_email', 'company_phone', 
                      'company_address', 'company_logo')
        }),
        ('Theme Customization', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('Status', {
            'fields': ('is_active', 'subscription_end_date')
        }),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    """
    Admin for Domain management.
    """
    list_display = ['domain', 'tenant', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['domain', 'tenant__name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with additional fields.
    """
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 
                   'is_active_employee', 'is_staff']
    list_filter = ['role', 'is_active_employee', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'employee_id']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 
                      'address', 'date_of_birth', 'profile_picture')
        }),
        ('Employment', {
            'fields': ('role', 'employee_id', 'department', 'hire_date', 
                      'salary', 'is_active_employee')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 
                      'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 
                      'first_name', 'last_name', 'role'),
        }),
    )


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """
    Admin for Role Permissions.
    """
    list_display = ['role', 'module_name', 'access_level', 'updated_at']
    list_filter = ['role', 'access_level', 'module_name']
    search_fields = ['role', 'module_name']
    ordering = ['role', 'module_name']
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('role', 'module_name', 'access_level')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """
    Admin for System Settings.
    """
    list_display = ['id', 'default_interest_rate', 'currency_code', 'updated_at']
    
    fieldsets = (
        ('Financial Settings', {
            'fields': ('default_interest_rate', 'late_payment_penalty', 
                      'currency_symbol', 'currency_code')
        }),
        ('Notification Settings', {
            'fields': ('payment_reminder_days', 'insurance_expiry_days')
        }),
        ('Document Settings', {
            'fields': ('max_document_size_mb',)
        }),
        ('Business Hours', {
            'fields': ('business_start_time', 'business_end_time')
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['updated_at']
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not SystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False