"""
Notifications App - Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages

from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    NotificationLog,
    NotificationSchedule
)


class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    readonly_fields = ['delivery_method', 'status', 'recipient', 'sent_at', 'delivered_at', 'error_message']
    can_delete = False
    max_num = 10
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title_short',
        'user_link',
        'notification_type_badge',
        'priority_badge',
        'is_read_icon',
        'is_sent',
        'created_at',
        'read_at',
    ]
    list_filter = [
        'notification_type',
        'priority',
        'is_read',
        'is_sent',
        'email_sent',
        'sms_sent',
        'created_at',
    ]
    search_fields = [
        'title',
        'message',
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
    ]
    readonly_fields = [
        'id',
        'related_object',
        'is_read',
        'read_at',
        'is_sent',
        'sent_at',
        'is_dismissed',
        'dismissed_at',
        'created_at',
        'updated_at',
        'age_display',
        'is_expired',
    ]
    fieldsets = (
        ('Recipient', {
            'fields': ('user',)
        }),
        ('Content', {
            'fields': ('title', 'message', 'notification_type', 'priority')
        }),
        ('Related Object', {
            'fields': (
                'content_type',
                'object_id',
                'related_object',
                'related_object_type',
                'related_object_id',
                'related_object_url'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_read',
                'read_at',
                'is_sent',
                'sent_at',
                'is_dismissed',
                'dismissed_at'
            )
        }),
        ('Delivery', {
            'fields': (
                'delivery_methods',
                'email_sent',
                'sms_sent',
                'push_sent'
            )
        }),
        ('Action', {
            'fields': ('action_text', 'action_url')
        }),
        ('Additional', {
            'fields': ('metadata', 'group_key', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'age_display', 'is_expired'),
            'classes': ('collapse',)
        })
    )
    inlines = [NotificationLogInline]
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = [
        'mark_as_read',
        'mark_as_unread',
        'dismiss_notifications',
        'resend_notifications',
        'delete_old_notifications'
    ]
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('user', 'content_type')
        return queryset
    
    def title_short(self, obj):
        if len(obj.title) > 50:
            return f"{obj.title[:47]}..."
        return obj.title
    title_short.short_description = 'Title'
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def notification_type_badge(self, obj):
        colors = {
            'success': 'green',
            'error': 'red',
            'warning': 'orange',
            'info': 'blue',
            'payment': 'purple',
            'auction': 'teal',
        }
        color = colors.get(obj.notification_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Type'
    
    def priority_badge(self, obj):
        colors = {
            'urgent': 'red',
            'high': 'orange',
            'medium': 'blue',
            'low': 'gray',
        }
        color = colors.get(obj.priority, 'gray')
        icon = '🔥' if obj.priority == 'urgent' else ''
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{} {}</span>',
            color,
            icon,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def is_read_icon(self, obj):
        if obj.is_read:
            return format_html('<span style="color: green; font-size: 16px;">✓</span>')
        return format_html('<span style="color: orange; font-size: 16px;">●</span>')
    is_read_icon.short_description = 'Read'
    is_read_icon.admin_order_field = 'is_read'
    
    def age_display(self, obj):
        age = obj.age
        if age.days > 0:
            return f"{age.days} days ago"
        hours = age.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        minutes = (age.seconds % 3600) // 60
        return f"{minutes} minutes ago"
    age_display.short_description = 'Age'
    
    def mark_as_read(self, request, queryset):
        updated = 0
        for notification in queryset.filter(is_read=False):
            notification.mark_as_read()
            updated += 1
        self.message_user(request, f'{updated} notification(s) marked as read.', messages.SUCCESS)
    mark_as_read.short_description = 'Mark selected as read'
    
    def mark_as_unread(self, request, queryset):
        updated = 0
        for notification in queryset.filter(is_read=True):
            notification.mark_as_unread()
            updated += 1
        self.message_user(request, f'{updated} notification(s) marked as unread.', messages.SUCCESS)
    mark_as_unread.short_description = 'Mark selected as unread'
    
    def dismiss_notifications(self, request, queryset):
        updated = 0
        for notification in queryset.filter(is_dismissed=False):
            notification.dismiss()
            updated += 1
        self.message_user(request, f'{updated} notification(s) dismissed.', messages.SUCCESS)
    dismiss_notifications.short_description = 'Dismiss selected notifications'
    
    def resend_notifications(self, request, queryset):
        count = queryset.update(is_sent=False, email_sent=False, sms_sent=False)
        self.message_user(request, f'{count} notification(s) queued for resending.', messages.SUCCESS)
    resend_notifications.short_description = 'Resend selected notifications'
    
    def delete_old_notifications(self, request, queryset):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=90)
        count = queryset.filter(created_at__lt=cutoff, is_read=True).delete()[0]
        self.message_user(request, f'{count} old notification(s) deleted.', messages.SUCCESS)
    delete_old_notifications.short_description = 'Delete old read notifications (90+ days)'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'enabled',
        'in_app_enabled',
        'email_enabled',
        'sms_enabled',
        'push_enabled',
        'email_digest',
        'quiet_hours_enabled',
    ]
    list_filter = [
        'enabled',
        'in_app_enabled',
        'email_enabled',
        'sms_enabled',
        'push_enabled',
        'email_digest',
        'quiet_hours_enabled',
    ]
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'phone_number',
    ]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('User', {
            'fields': ('user', 'enabled')
        }),
        ('Delivery Methods', {
            'fields': (
                'in_app_enabled',
                'email_enabled',
                'email_address',
                'email_digest',
                'email_digest_time',
                'sms_enabled',
                'phone_number',
                'push_enabled'
            )
        }),
        ('Notification Types', {
            'fields': (
                'notify_payment',
                'notify_vehicle',
                'notify_auction',
                'notify_document',
                'notify_insurance',
                'notify_repossession',
                'notify_expense',
                'notify_payroll',
                'notify_system'
            )
        }),
        ('Priority Filters', {
            'fields': ('notify_urgent_only', 'notify_high_and_urgent')
        }),
        ('Quiet Hours', {
            'fields': (
                'quiet_hours_enabled',
                'quiet_hours_start',
                'quiet_hours_end'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    actions = ['enable_all', 'disable_all', 'enable_email', 'disable_email']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def enable_all(self, request, queryset):
        updated = queryset.update(enabled=True)
        self.message_user(request, f'{updated} preference(s) enabled.', messages.SUCCESS)
    enable_all.short_description = 'Enable notifications for selected users'
    
    def disable_all(self, request, queryset):
        updated = queryset.update(enabled=False)
        self.message_user(request, f'{updated} preference(s) disabled.', messages.SUCCESS)
    disable_all.short_description = 'Disable notifications for selected users'
    
    def enable_email(self, request, queryset):
        updated = queryset.update(email_enabled=True)
        self.message_user(request, f'{updated} email notification(s) enabled.', messages.SUCCESS)
    enable_email.short_description = 'Enable email notifications'
    
    def disable_email(self, request, queryset):
        updated = queryset.update(email_enabled=False)
        self.message_user(request, f'{updated} email notification(s) disabled.', messages.SUCCESS)
    disable_email.short_description = 'Disable email notifications'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'template_type',
        'notification_type',
        'priority',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'template_type',
        'notification_type',
        'priority',
        'is_active',
    ]
    search_fields = ['name', 'description', 'title_template', 'message_template']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Template Type', {
            'fields': ('template_type', 'notification_type', 'priority')
        }),
        ('Content', {
            'fields': ('title_template', 'message_template')
        }),
        ('Email Specific', {
            'fields': ('subject_template', 'html_template'),
            'classes': ('collapse',)
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


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'notification_link',
        'delivery_method',
        'status_badge',
        'recipient',
        'created_at',
        'sent_at',
        'delivered_at',
        'retry_count',
    ]
    list_filter = [
        'delivery_method',
        'status',
        'provider',
        'created_at',
    ]
    search_fields = [
        'recipient',
        'external_id',
        'error_message',
        'notification__title',
    ]
    readonly_fields = [
        'notification',
        'delivery_method',
        'recipient',
        'created_at',
        'sent_at',
        'delivered_at',
        'external_id',
        'provider',
        'metadata',
    ]
    fieldsets = (
        ('Notification', {
            'fields': ('notification',)
        }),
        ('Delivery', {
            'fields': ('delivery_method', 'recipient', 'status')
        }),
        ('Timing', {
            'fields': ('created_at', 'sent_at', 'delivered_at')
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count')
        }),
        ('External', {
            'fields': ('external_id', 'provider', 'metadata'),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'created_at'
    list_per_page = 100
    actions = ['retry_failed']
    
    def has_add_permission(self, request):
        return False
    
    def notification_link(self, obj):
        url = reverse('admin:notifications_notification_change', args=[obj.notification.pk])
        return format_html('<a href="{}">{}</a>', url, obj.notification.title[:30])
    notification_link.short_description = 'Notification'
    
    def status_badge(self, obj):
        colors = {
            'sent': 'green',
            'delivered': 'darkgreen',
            'failed': 'red',
            'bounced': 'orange',
            'pending': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def retry_failed(self, request, queryset):
        count = 0
        for log in queryset.filter(status='failed'):
            log.status = 'pending'
            log.save(update_fields=['status'])
            count += 1
        self.message_user(request, f'{count} log(s) queued for retry.', messages.SUCCESS)
    retry_failed.short_description = 'Retry failed deliveries'


@admin.register(NotificationSchedule)
class NotificationScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'frequency',
        'status_badge',
        'scheduled_time',
        'next_run',
        'last_run',
        'is_active',
    ]
    list_filter = [
        'frequency',
        'status',
        'is_active',
        'scheduled_time',
    ]
    search_fields = ['name', 'description', 'title', 'message']
    readonly_fields = ['id', 'next_run', 'last_run', 'created_at', 'updated_at']
    filter_horizontal = ['users']
    fieldsets = (
        ('Schedule Information', {
            'fields': ('name', 'description', 'status', 'is_active')
        }),
        ('Template or Manual', {
            'fields': ('template', 'title', 'message', 'notification_type')
        }),
        ('Recipients', {
            'fields': ('users', 'user_filter')
        }),
        ('Schedule Settings', {
            'fields': (
                'frequency',
                'scheduled_time',
                'next_run',
                'last_run'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    actions = ['activate_schedules', 'pause_schedules', 'run_now']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.next_run = obj.scheduled_time
        super().save_model(request, obj, form, change)
    
    def status_badge(self, obj):
        colors = {
            'active': 'green',
            'paused': 'orange',
            'completed': 'blue',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def activate_schedules(self, request, queryset):
        updated = queryset.update(status='active', is_active=True)
        self.message_user(request, f'{updated} schedule(s) activated.', messages.SUCCESS)
    activate_schedules.short_description = 'Activate selected schedules'
    
    def pause_schedules(self, request, queryset):
        updated = queryset.update(status='paused', is_active=False)
        self.message_user(request, f'{updated} schedule(s) paused.', messages.SUCCESS)
    pause_schedules.short_description = 'Pause selected schedules'
    
    def run_now(self, request, queryset):
        count = 0
        for schedule in queryset:
            # Trigger immediate execution (would be handled by task)
            schedule.next_run = timezone.now()
            schedule.save(update_fields=['next_run'])
            count += 1
        self.message_user(request, f'{count} schedule(s) queued for immediate execution.', messages.SUCCESS)
    run_now.short_description = 'Run selected schedules now'