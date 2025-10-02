"""
Notifications App - Models
Handles system-wide notification management
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


# ============================================================================
# CUSTOM MANAGERS
# ============================================================================

class NotificationManager(models.Manager):
    """Custom manager for Notification model"""
    
    def unread(self):
        """Get unread notifications"""
        return self.filter(is_read=False)
    
    def read(self):
        """Get read notifications"""
        return self.filter(is_read=True)
    
    def for_user(self, user):
        """Get notifications for specific user"""
        return self.filter(user=user)
    
    def unread_for_user(self, user):
        """Get unread notifications for user"""
        return self.filter(user=user, is_read=False)
    
    def by_priority(self, priority):
        """Get notifications by priority"""
        return self.filter(priority=priority)
    
    def urgent(self):
        """Get urgent notifications"""
        return self.filter(priority='urgent')
    
    def recent(self, days=7):
        """Get recent notifications"""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
    
    def mark_as_read(self, user):
        """Mark all notifications as read for user"""
        return self.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )


# ============================================================================
# NOTIFICATION MODEL
# ============================================================================

class Notification(models.Model):
    """
    Main notification model for system-wide notifications
    """
    
    NOTIFICATION_TYPE_CHOICES = [
        ('system', 'System'),
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('payment', 'Payment'),
        ('vehicle', 'Vehicle'),
        ('client', 'Client'),
        ('auction', 'Auction'),
        ('bid', 'Bid'),
        ('document', 'Document'),
        ('insurance', 'Insurance'),
        ('repossession', 'Repossession'),
        ('expense', 'Expense'),
        ('payroll', 'Payroll'),
        ('registration', 'Registration'),
        ('delivery', 'Delivery'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('note', 'Note'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    DELIVERY_METHOD_CHOICES = [
        ('in_app', 'In-App'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    
    # Notification Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='info',
        db_index=True
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True
    )
    
    # Generic Foreign Key for related object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Alternative related object tracking
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    related_object_url = models.CharField(max_length=500, blank=True)
    
    # Status Fields
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery Methods
    delivery_methods = models.JSONField(
        default=list,
        blank=True,
        help_text="List of delivery methods: in_app, email, sms, push"
    )
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    
    # Action & Link
    action_text = models.CharField(max_length=100, blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Grouping
    group_key = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Key for grouping related notifications"
    )
    
    objects = NotificationManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', 'notification_type']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['group_key']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])
    
    def dismiss(self):
        """Dismiss notification"""
        if not self.is_dismissed:
            self.is_dismissed = True
            self.dismissed_at = timezone.now()
            self.save(update_fields=['is_dismissed', 'dismissed_at'])
    
    @property
    def is_expired(self):
        """Check if notification has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def age(self):
        """Get notification age"""
        return timezone.now() - self.created_at
    
    def get_icon(self):
        """Get icon based on notification type and priority"""
        icons = {
            'success': 'check-circle',
            'error': 'x-circle',
            'warning': 'alert-triangle',
            'info': 'info',
            'payment': 'dollar-sign',
            'vehicle': 'truck',
            'auction': 'gavel',
            'urgent': 'alert-circle',
        }
        
        if self.priority == 'urgent':
            return icons.get('urgent', 'bell')
        
        return icons.get(self.notification_type, 'bell')
    
    def get_color(self):
        """Get color class based on type and priority"""
        if self.priority == 'urgent':
            return 'danger'
        
        colors = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info',
            'high': 'warning',
            'medium': 'primary',
            'low': 'secondary',
        }
        
        return colors.get(self.notification_type, colors.get(self.priority, 'info'))


# ============================================================================
# NOTIFICATION PREFERENCE MODEL
# ============================================================================

class NotificationPreference(models.Model):
    """
    User preferences for notification delivery
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Global Settings
    enabled = models.BooleanField(default=True)
    
    # In-App Notifications
    in_app_enabled = models.BooleanField(default=True)
    
    # Email Notifications
    email_enabled = models.BooleanField(default=True)
    email_address = models.EmailField(
        blank=True,
        validators=[EmailValidator()],
        help_text="Override default email"
    )
    email_digest = models.BooleanField(
        default=False,
        help_text="Receive daily email digest instead of individual emails"
    )
    email_digest_time = models.TimeField(
        default=timezone.now().replace(hour=9, minute=0, second=0).time(),
        help_text="Time to send daily digest"
    )
    
    # SMS Notifications
    sms_enabled = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Push Notifications
    push_enabled = models.BooleanField(default=True)
    
    # Notification Type Preferences
    notify_payment = models.BooleanField(default=True)
    notify_vehicle = models.BooleanField(default=True)
    notify_auction = models.BooleanField(default=True)
    notify_document = models.BooleanField(default=True)
    notify_insurance = models.BooleanField(default=True)
    notify_repossession = models.BooleanField(default=True)
    notify_expense = models.BooleanField(default=True)
    notify_payroll = models.BooleanField(default=True)
    notify_system = models.BooleanField(default=True)
    
    # Priority Filters
    notify_urgent_only = models.BooleanField(
        default=False,
        help_text="Only receive urgent notifications"
    )
    notify_high_and_urgent = models.BooleanField(
        default=False,
        help_text="Only receive high and urgent notifications"
    )
    
    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(
        default=timezone.now().replace(hour=22, minute=0, second=0).time()
    )
    quiet_hours_end = models.TimeField(
        default=timezone.now().replace(hour=8, minute=0, second=0).time()
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    def should_notify(self, notification_type, priority='medium'):
        """Check if user should receive notification"""
        
        if not self.enabled:
            return False
        
        # Check priority filters
        if self.notify_urgent_only and priority != 'urgent':
            return False
        
        if self.notify_high_and_urgent and priority not in ['high', 'urgent']:
            return False
        
        # Check notification type
        type_field = f'notify_{notification_type}'
        if hasattr(self, type_field):
            return getattr(self, type_field)
        
        return True
    
    def is_quiet_hours(self):
        """Check if current time is in quiet hours"""
        
        if not self.quiet_hours_enabled:
            return False
        
        now = timezone.now().time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        
        if start < end:
            return start <= now <= end
        else:  # Crosses midnight
            return now >= start or now <= end
    
    def get_delivery_methods(self, priority='medium'):
        """Get enabled delivery methods for notification"""
        
        methods = []
        
        # Skip if in quiet hours (except urgent)
        if self.is_quiet_hours() and priority != 'urgent':
            return methods
        
        if self.in_app_enabled:
            methods.append('in_app')
        
        if self.email_enabled and not self.email_digest:
            methods.append('email')
        
        if self.sms_enabled and priority in ['high', 'urgent']:
            methods.append('sms')
        
        if self.push_enabled:
            methods.append('push')
        
        return methods


# ============================================================================
# NOTIFICATION TEMPLATE MODEL
# ============================================================================

class NotificationTemplate(models.Model):
    """
    Reusable notification templates
    """
    
    TEMPLATE_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('in_app', 'In-App'),
        ('push', 'Push'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Template Type
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    notification_type = models.CharField(max_length=20, choices=Notification.NOTIFICATION_TYPE_CHOICES)
    
    # Template Content
    title_template = models.CharField(max_length=255)
    message_template = models.TextField()
    
    # Email Specific
    subject_template = models.CharField(max_length=255, blank=True)
    html_template = models.TextField(blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    priority = models.CharField(
        max_length=10,
        choices=Notification.PRIORITY_CHOICES,
        default='medium'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_templates'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, context):
        """Render template with context variables"""
        from django.template import Template, Context
        
        title = Template(self.title_template).render(Context(context))
        message = Template(self.message_template).render(Context(context))
        
        result = {
            'title': title,
            'message': message,
        }
        
        if self.subject_template:
            result['subject'] = Template(self.subject_template).render(Context(context))
        
        if self.html_template:
            result['html'] = Template(self.html_template).render(Context(context))
        
        return result


# ============================================================================
# NOTIFICATION LOG MODEL
# ============================================================================

class NotificationLog(models.Model):
    """
    Log of all notification delivery attempts
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('delivered', 'Delivered'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    # Delivery Details
    delivery_method = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recipient = models.CharField(max_length=255)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Error Tracking
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    # External IDs
    external_id = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification', 'delivery_method']),
            models.Index(fields=['status', '-created_at']),
        ]
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
    
    def __str__(self):
        return f"{self.delivery_method} - {self.status} - {self.recipient}"
    
    def mark_as_sent(self):
        """Mark log as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_delivered(self):
        """Mark log as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def mark_as_failed(self, error_message):
        """Mark log as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])


# ============================================================================
# NOTIFICATION SCHEDULE MODEL
# ============================================================================

class NotificationSchedule(models.Model):
    """
    Schedule notifications to be sent at specific times
    """
    
    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Schedule Details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Template or Manual
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Manual notification content
    title = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    notification_type = models.CharField(
        max_length=20,
        choices=Notification.NOTIFICATION_TYPE_CHOICES,
        default='info'
    )
    
    # Recipients
    users = models.ManyToManyField(User, related_name='scheduled_notifications')
    user_filter = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter criteria for dynamic user selection"
    )
    
    # Schedule Settings
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once')
    scheduled_time = models.DateTimeField()
    next_run = models.DateTimeField(null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_schedules'
    )
    
    class Meta:
        ordering = ['scheduled_time']
        verbose_name = 'Notification Schedule'
        verbose_name_plural = 'Notification Schedules'
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"