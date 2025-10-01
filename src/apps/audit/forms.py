"""
Audit Models
Track all user actions and system changes
"""
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from utils.constants import AuditAction
import json


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog with helper methods"""
    
    def log_action(self, user, action, description, **kwargs):
        """
        Helper method to create audit log entries
        """
        return self.create(
            user=user,
            action=action,
            description=description,
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            model_name=kwargs.get('model_name'),
            object_id=kwargs.get('object_id'),
            changes=kwargs.get('changes'),
            request_path=kwargs.get('request_path'),
            request_method=kwargs.get('request_method'),
        )
    
    def user_activity(self, user):
        """Get all activity for a specific user"""
        return self.filter(user=user).order_by('-timestamp')
    
    def recent_activity(self, days=7):
        """Get recent activity within specified days"""
        from django.utils import timezone
        from datetime import timedelta
        
        since = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=since).order_by('-timestamp')
    
    def by_model(self, model_name):
        """Get all logs for a specific model"""
        return self.filter(model_name=model_name).order_by('-timestamp')
    
    def by_action(self, action):
        """Get all logs for a specific action type"""
        return self.filter(action=action).order_by('-timestamp')


class AuditLog(models.Model):
    """
    Main audit log model
    Tracks all user actions and changes in the system
    """
    
    # User Information
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='User who performed the action'
    )
    
    # Action Information
    action = models.CharField(
        'Action Type',
        max_length=20,
        choices=AuditAction.CHOICES,
        db_index=True,
        help_text='Type of action performed'
    )
    
    description = models.TextField(
        'Description',
        help_text='Human-readable description of the action'
    )
    
    # Object Information (Generic Foreign Key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Type of object that was affected'
    )
    
    object_id = models.CharField(
        'Object ID',
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text='ID of the object that was affected'
    )
    
    content_object = GenericForeignKey('content_type', 'object_id')
    
    model_name = models.CharField(
        'Model Name',
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text='Name of the model that was affected'
    )
    
    # Change Details
    changes = models.JSONField(
        'Changes',
        null=True,
        blank=True,
        help_text='JSON object containing old and new values'
    )
    
    # Request Information
    ip_address = models.GenericIPAddressField(
        'IP Address',
        null=True,
        blank=True,
        help_text='IP address of the user'
    )
    
    user_agent = models.TextField(
        'User Agent',
        null=True,
        blank=True,
        help_text='Browser/client user agent string'
    )
    
    request_path = models.CharField(
        'Request Path',
        max_length=500,
        null=True,
        blank=True,
        help_text='URL path that was accessed'
    )
    
    request_method = models.CharField(
        'Request Method',
        max_length=10,
        null=True,
        blank=True,
        help_text='HTTP method (GET, POST, PUT, DELETE)'
    )
    
    # Additional Data
    additional_data = models.JSONField(
        'Additional Data',
        null=True,
        blank=True,
        help_text='Any additional contextual data'
    )
    
    # Timestamp
    timestamp = models.DateTimeField(
        'Timestamp',
        auto_now_add=True,
        db_index=True,
        help_text='When the action occurred'
    )
    
    # Custom manager
    objects = AuditLogManager()
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['model_name', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]
    
    def __str__(self):
        user_str = self.user.get_full_name() if self.user else 'Anonymous'
        return f"{user_str} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def get_changes_summary(self):
        """Get a formatted summary of changes"""
        if not self.changes:
            return "No changes recorded"
        
        summary = []
        for field, values in self.changes.items():
            if isinstance(values, dict) and 'old' in values and 'new' in values:
                summary.append(f"{field}: {values['old']} → {values['new']}")
            else:
                summary.append(f"{field}: {values}")
        
        return "\n".join(summary)
    
    def get_action_color(self):
        """Get color code for action badge"""
        color_map = {
            AuditAction.CREATE: 'green',
            AuditAction.READ: 'blue',
            AuditAction.UPDATE: 'yellow',
            AuditAction.DELETE: 'red',
            AuditAction.LOGIN: 'green',
            AuditAction.LOGOUT: 'gray',
            AuditAction.EXPORT: 'purple',
        }
        return color_map.get(self.action, 'gray')
    
    def get_action_icon(self):
        """Get icon for action type"""
        icon_map = {
            AuditAction.CREATE: 'fa-plus-circle',
            AuditAction.READ: 'fa-eye',
            AuditAction.UPDATE: 'fa-edit',
            AuditAction.DELETE: 'fa-trash',
            AuditAction.LOGIN: 'fa-sign-in-alt',
            AuditAction.LOGOUT: 'fa-sign-out-alt',
            AuditAction.EXPORT: 'fa-download',
        }
        return icon_map.get(self.action, 'fa-info-circle')
    
    @property
    def user_display(self):
        """Get user display name"""
        if self.user:
            return f"{self.user.get_full_name()} ({self.user.email})"
        return "System/Anonymous"
    
    @property
    def formatted_timestamp(self):
        """Get formatted timestamp"""
        return self.timestamp.strftime('%B %d, %Y at %I:%M %p')
    
    @classmethod
    def log_create(cls, user, obj, description=None, **kwargs):
        """Log object creation"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.CREATE,
            description=description or f"Created {obj.__class__.__name__}: {obj}",
            model_name=obj.__class__.__name__,
            object_id=str(obj.pk),
            **kwargs
        )
    
    @classmethod
    def log_update(cls, user, obj, changes, description=None, **kwargs):
        """Log object update"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.UPDATE,
            description=description or f"Updated {obj.__class__.__name__}: {obj}",
            model_name=obj.__class__.__name__,
            object_id=str(obj.pk),
            changes=changes,
            **kwargs
        )
    
    @classmethod
    def log_delete(cls, user, obj, description=None, **kwargs):
        """Log object deletion"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.DELETE,
            description=description or f"Deleted {obj.__class__.__name__}: {obj}",
            model_name=obj.__class__.__name__,
            object_id=str(obj.pk),
            **kwargs
        )
    
    @classmethod
    def log_read(cls, user, obj, description=None, **kwargs):
        """Log object read/view"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.READ,
            description=description or f"Viewed {obj.__class__.__name__}: {obj}",
            model_name=obj.__class__.__name__,
            object_id=str(obj.pk),
            **kwargs
        )
    
    @classmethod
    def log_login(cls, user, **kwargs):
        """Log user login"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.LOGIN,
            description=f"User logged in: {user.email}",
            **kwargs
        )
    
    @classmethod
    def log_logout(cls, user, **kwargs):
        """Log user logout"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.LOGOUT,
            description=f"User logged out: {user.email}",
            **kwargs
        )
    
    @classmethod
    def log_export(cls, user, model_name, description=None, **kwargs):
        """Log data export"""
        return cls.objects.log_action(
            user=user,
            action=AuditAction.EXPORT,
            description=description or f"Exported {model_name} data",
            model_name=model_name,
            **kwargs
        )


class LoginHistory(models.Model):
    """
    Separate model to track login attempts and sessions
    More detailed than AuditLog for security purposes
    """
    
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='login_history',
        null=True,
        blank=True
    )
    
    email_attempted = models.EmailField(
        'Email Attempted',
        help_text='Email address used in login attempt'
    )
    
    success = models.BooleanField(
        'Success',
        default=False,
        help_text='Whether login was successful'
    )
    
    failure_reason = models.CharField(
        'Failure Reason',
        max_length=255,
        null=True,
        blank=True,
        help_text='Reason for failed login'
    )
    
    ip_address = models.GenericIPAddressField(
        'IP Address',
        null=True,
        blank=True
    )
    
    user_agent = models.TextField(
        'User Agent',
        null=True,
        blank=True
    )
    
    location = models.CharField(
        'Location',
        max_length=255,
        null=True,
        blank=True,
        help_text='Approximate location based on IP'
    )
    
    session_key = models.CharField(
        'Session Key',
        max_length=100,
        null=True,
        blank=True
    )
    
    logout_time = models.DateTimeField(
        'Logout Time',
        null=True,
        blank=True
    )
    
    timestamp = models.DateTimeField(
        'Login Time',
        auto_now_add=True,
        db_index=True
    )
    
    class Meta:
        db_table = 'login_history'
        verbose_name = 'Login History'
        verbose_name_plural = 'Login History'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['success', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.email_attempted} - {status} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @property
    def duration(self):
        """Calculate session duration"""
        if self.logout_time:
            delta = self.logout_time - self.timestamp
            return delta
        return None
    
    @property
    def is_suspicious(self):
        """Check if login attempt is suspicious"""
        if not self.success:
            # Check for multiple failed attempts from same IP
            recent_failures = LoginHistory.objects.filter(
                ip_address=self.ip_address,
                success=False,
                timestamp__gte=self.timestamp
            ).count()
            return recent_failures >= 3
        return False