"""
Authentication Admin Configuration
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """Inline admin for user profile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fields = (
        'bio', 'date_of_birth', 'national_id',
        'emergency_contact_name', 'emergency_contact_phone',
        'emergency_contact_relationship',
        'email_notifications', 'sms_notifications'
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    inlines = [UserProfileInline]
    
    list_display = [
        'email', 'full_name', 'role_badge', 'phone',
        'is_active', 'is_staff', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone', 'employee_id']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone', 'profile_picture', 'address', 'city')
        }),
        ('Employment Information', {
            'fields': ('role', 'employee_id', 'department', 'hire_date')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Authentication', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Personal Information', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'phone'),
        }),
        ('Role', {
            'classes': ('wide',),
            'fields': ('role', 'is_active', 'is_staff'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']
    
    def full_name(self, obj):
        """Display full name"""
        return obj.get_full_name()
    full_name.short_description = 'Full Name'
    
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
    
    def save_model(self, request, obj, form, change):
        """Override save to handle profile creation"""
        super().save_model(request, obj, form, change)
        # Create profile if it doesn't exist
        UserProfile.objects.get_or_create(user=obj)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User Profile Admin"""
    list_display = ['user', 'date_of_birth', 'national_id', 'email_notifications', 'sms_notifications']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'national_id']
    list_filter = ['email_notifications', 'sms_notifications']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('bio', 'date_of_birth', 'national_id')
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name',
                'emergency_contact_phone',
                'emergency_contact_relationship'
            )
        }),
        ('Notification Preferences', {
            'fields': ('email_notifications', 'sms_notifications')
        }),
    )