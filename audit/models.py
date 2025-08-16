# audit/models.py

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone


class AuditLog(models.Model):
    """
    Main audit log model to track all user actions system-wide
    """
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('VIEW', 'View'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('PRINT', 'Print'),
        ('DOWNLOAD', 'Download'),
        ('UPLOAD', 'Upload'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    # User who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    
    # Action details
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='LOW')
    
    # Generic foreign key to track any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional context
    module_name = models.CharField(max_length=100)  # e.g., 'Vehicle Inventory', 'Client Management'
    table_name = models.CharField(max_length=100, null=True, blank=True)  # Database table name
    record_id = models.CharField(max_length=100, null=True, blank=True)  # ID of the affected record
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)  # GET, POST, PUT, DELETE
    request_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Data changes (for UPDATE actions)
    old_values = models.JSONField(null=True, blank=True)  # Previous values
    new_values = models.JSONField(null=True, blank=True)  # New values
    changed_fields = models.JSONField(null=True, blank=True)  # List of changed field names
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    
    # Status and flags
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)  # For sensitive operations
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['module_name', 'timestamp']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_successful']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action_type} - {self.module_name} - {self.timestamp}"
    
    @property
    def formatted_timestamp(self):
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_changes_summary(self):
        """Return a human-readable summary of changes"""
        if not self.changed_fields:
            return "No changes tracked"
        
        changes = []
        for field in self.changed_fields:
            old_val = self.old_values.get(field, 'N/A') if self.old_values else 'N/A'
            new_val = self.new_values.get(field, 'N/A') if self.new_values else 'N/A'
            changes.append(f"{field}: {old_val} → {new_val}")
        
        return "; ".join(changes)


class LoginAttempt(models.Model):
    """
    Track login attempts (successful and failed)
    """
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(null=True, blank=True)
    is_successful = models.BooleanField()
    failure_reason = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Link to user if login was successful
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='login_attempts'
    )
    
    class Meta:
        db_table = 'login_attempts'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['is_successful']),
        ]
    
    def __str__(self):
        status = "SUCCESS" if self.is_successful else "FAILED"
        return f"{self.username} - {status} - {self.timestamp}"


class UserSession(models.Model):
    """
    Track active user sessions
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(null=True, blank=True)
    login_time = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time}"
    
    @property
    def session_duration(self):
        """Calculate session duration"""
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time


class SystemEvent(models.Model):
    """
    Track system-level events (not user-specific)
    """
    EVENT_TYPES = [
        ('SYSTEM_START', 'System Start'),
        ('SYSTEM_SHUTDOWN', 'System Shutdown'),
        ('DATABASE_BACKUP', 'Database Backup'),
        ('DATABASE_RESTORE', 'Database Restore'),
        ('MAINTENANCE_START', 'Maintenance Start'),
        ('MAINTENANCE_END', 'Maintenance End'),
        ('SECURITY_ALERT', 'Security Alert'),
        ('ERROR', 'System Error'),
        ('WARNING', 'System Warning'),
        ('INFO', 'System Information'),
    ]
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField()
    details = models.JSONField(null=True, blank=True)
    severity = models.CharField(max_length=10, choices=AuditLog.SEVERITY_CHOICES, default='LOW')
    timestamp = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_events'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'system_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['severity']),
            models.Index(fields=['resolved']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.timestamp}"


class DataExport(models.Model):
    """
    Track data exports for compliance
    """
    EXPORT_TYPES = [
        ('PDF', 'PDF Document'),
        ('CSV', 'CSV File'),
        ('EXCEL', 'Excel File'),
        ('JSON', 'JSON Data'),
        ('XML', 'XML Data'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exports')
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    module_name = models.CharField(max_length=100)
    description = models.TextField()
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # in bytes
    record_count = models.PositiveIntegerField(null=True, blank=True)
    filters_applied = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'data_exports'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['module_name', 'timestamp']),
            models.Index(fields=['export_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.export_type} - {self.module_name} - {self.timestamp}"
    
    @property
    def formatted_file_size(self):
        """Return human-readable file size"""
        if not self.file_size:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024
        return f"{self.file_size:.1f} TB"


class ComplianceReport(models.Model):
    """
    Generate and track compliance reports
    """
    REPORT_TYPES = [
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('QUARTERLY', 'Quarterly Report'),
        ('ANNUAL', 'Annual Report'),
        ('CUSTOM', 'Custom Report'),
        ('INCIDENT', 'Incident Report'),
    ]
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='compliance_reports')
    generated_at = models.DateTimeField(default=timezone.now)
    
    # Report statistics
    total_actions = models.PositiveIntegerField(default=0)
    failed_actions = models.PositiveIntegerField(default=0)
    security_incidents = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    
    # File details
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'compliance_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['report_type', 'generated_at']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['generated_by']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.generated_at}"