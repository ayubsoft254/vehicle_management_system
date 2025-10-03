"""
Reports App - Models
Handles business intelligence and reporting
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import uuid
import json

User = get_user_model()


# ============================================================================
# CUSTOM MANAGERS
# ============================================================================

class ReportManager(models.Manager):
    """Custom manager for Report model"""
    
    def active(self):
        """Get active reports"""
        return self.filter(is_active=True)
    
    def by_type(self, report_type):
        """Get reports by type"""
        return self.filter(report_type=report_type)
    
    def scheduled(self):
        """Get scheduled reports"""
        return self.filter(is_scheduled=True, is_active=True)
    
    def recent(self, days=30):
        """Get recent reports"""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class ReportExecutionManager(models.Manager):
    """Custom manager for ReportExecution model"""
    
    def successful(self):
        """Get successful executions"""
        return self.filter(status='completed')
    
    def failed(self):
        """Get failed executions"""
        return self.filter(status='failed')
    
    def in_progress(self):
        """Get in-progress executions"""
        return self.filter(status='in_progress')


# ============================================================================
# REPORT MODEL
# ============================================================================

class Report(models.Model):
    """
    Main report definition model
    """
    
    REPORT_TYPE_CHOICES = [
        ('financial', 'Financial Report'),
        ('vehicle', 'Vehicle Report'),
        ('client', 'Client Report'),
        ('auction', 'Auction Report'),
        ('payment', 'Payment Report'),
        ('expense', 'Expense Report'),
        ('payroll', 'Payroll Report'),
        ('insurance', 'Insurance Report'),
        ('repossession', 'Repossession Report'),
        ('sales', 'Sales Report'),
        ('inventory', 'Inventory Report'),
        ('performance', 'Performance Report'),
        ('custom', 'Custom Report'),
    ]
    
    FREQUENCY_CHOICES = [
        ('once', 'One Time'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    OUTPUT_FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('html', 'HTML'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Report Type
    report_type = models.CharField(
        max_length=50,
        choices=REPORT_TYPE_CHOICES,
        db_index=True
    )
    
    # Configuration
    template = models.ForeignKey(
        'ReportTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    
    # Query & Filters
    query_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Query configuration and filters"
    )
    date_range_type = models.CharField(
        max_length=50,
        default='last_30_days',
        help_text="last_7_days, last_30_days, last_quarter, last_year, custom, etc."
    )
    custom_date_from = models.DateField(null=True, blank=True)
    custom_date_to = models.DateField(null=True, blank=True)
    
    # Output Settings
    output_format = models.CharField(
        max_length=20,
        choices=OUTPUT_FORMAT_CHOICES,
        default='pdf'
    )
    include_charts = models.BooleanField(default=True)
    include_summary = models.BooleanField(default=True)
    include_details = models.BooleanField(default=True)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='once'
    )
    schedule_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time to run scheduled report"
    )
    schedule_day = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of month for monthly reports"
    )
    next_run = models.DateTimeField(null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(
        User,
        related_name='subscribed_reports',
        blank=True
    )
    email_recipients = models.TextField(
        blank=True,
        help_text="Additional email addresses (comma-separated)"
    )
    send_email = models.BooleanField(default=True)
    
    # Access Control
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_reports'
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Allow all users to view this report"
    )
    allowed_users = models.ManyToManyField(
        User,
        related_name='accessible_reports',
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Statistics
    execution_count = models.IntegerField(default=0)
    last_execution_status = models.CharField(max_length=20, blank=True)
    average_execution_time = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average execution time in seconds"
    )
    
    objects = ReportManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'is_active']),
            models.Index(fields=['is_scheduled', 'next_run']),
            models.Index(fields=['created_by']),
        ]
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"
    
    def can_user_access(self, user):
        """Check if user can access this report"""
        if user.is_staff or user.is_superuser:
            return True
        if self.created_by == user:
            return True
        if self.is_public:
            return True
        if user in self.allowed_users.all():
            return True
        return False
    
    def get_date_range(self):
        """Get the date range for the report"""
        from datetime import timedelta
        
        today = timezone.now().date()
        
        if self.date_range_type == 'custom':
            return self.custom_date_from, self.custom_date_to
        elif self.date_range_type == 'today':
            return today, today
        elif self.date_range_type == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif self.date_range_type == 'last_7_days':
            return today - timedelta(days=7), today
        elif self.date_range_type == 'last_30_days':
            return today - timedelta(days=30), today
        elif self.date_range_type == 'last_quarter':
            return today - timedelta(days=90), today
        elif self.date_range_type == 'last_year':
            return today - timedelta(days=365), today
        elif self.date_range_type == 'month_to_date':
            return today.replace(day=1), today
        elif self.date_range_type == 'year_to_date':
            return today.replace(month=1, day=1), today
        
        return None, None
    
    def calculate_next_run(self):
        """Calculate next scheduled run time"""
        from datetime import timedelta
        
        if not self.is_scheduled or not self.schedule_time:
            return None
        
        now = timezone.now()
        next_run = now.replace(
            hour=self.schedule_time.hour,
            minute=self.schedule_time.minute,
            second=0,
            microsecond=0
        )
        
        if self.frequency == 'daily':
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif self.frequency == 'weekly':
            if next_run <= now:
                next_run += timedelta(weeks=1)
        
        elif self.frequency == 'biweekly':
            if next_run <= now:
                next_run += timedelta(weeks=2)
        
        elif self.frequency == 'monthly':
            if self.schedule_day:
                next_run = next_run.replace(day=min(self.schedule_day, 28))
            if next_run <= now:
                # Move to next month
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
        
        elif self.frequency == 'quarterly':
            if next_run <= now:
                next_run += timedelta(days=90)
        
        elif self.frequency == 'yearly':
            if next_run <= now:
                next_run = next_run.replace(year=next_run.year + 1)
        
        return next_run
    
    def get_email_recipients_list(self):
        """Get list of all email recipients"""
        emails = []
        
        # Add user recipients
        for user in self.recipients.all():
            if user.email:
                emails.append(user.email)
        
        # Add additional emails
        if self.email_recipients:
            additional = [e.strip() for e in self.email_recipients.split(',')]
            emails.extend(additional)
        
        return list(set(emails))  # Remove duplicates


# ============================================================================
# REPORT TEMPLATE MODEL
# ============================================================================

class ReportTemplate(models.Model):
    """
    Reusable report templates
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Template Type
    report_type = models.CharField(
        max_length=50,
        choices=Report.REPORT_TYPE_CHOICES
    )
    
    # Template Configuration
    layout = models.CharField(
        max_length=50,
        default='standard',
        help_text="standard, detailed, summary, etc."
    )
    columns = models.JSONField(
        default=list,
        blank=True,
        help_text="List of columns to include"
    )
    grouping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Grouping configuration"
    )
    sorting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sorting configuration"
    )
    aggregations = models.JSONField(
        default=list,
        blank=True,
        help_text="Aggregation functions to apply"
    )
    
    # Visual Settings
    header_template = models.TextField(blank=True)
    footer_template = models.TextField(blank=True)
    css_styles = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_report_templates'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


# ============================================================================
# REPORT EXECUTION MODEL
# ============================================================================

class ReportExecution(models.Model):
    """
    Track report execution history
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # Execution Details
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_executions'
    )
    is_scheduled = models.BooleanField(
        default=False,
        help_text="Was this execution triggered by schedule?"
    )
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Execution time in seconds"
    )
    
    # Date Range Used
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    
    # Output
    output_format = models.CharField(max_length=20)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    
    # Results
    result_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Report result data/summary"
    )
    row_count = models.IntegerField(null=True, blank=True)
    
    # Error Tracking
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Execution parameters"
    )
    
    objects = ReportExecutionManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['triggered_by']),
        ]
        verbose_name = 'Report Execution'
        verbose_name_plural = 'Report Executions'
    
    def __str__(self):
        return f"{self.report.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def mark_as_started(self):
        """Mark execution as started"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_as_completed(self, file_path=None, file_size=None, row_count=None):
        """Mark execution as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.execution_time = Decimal(str(duration))
        
        if file_path:
            self.file_path = file_path
        if file_size:
            self.file_size = file_size
        if row_count:
            self.row_count = row_count
        
        self.save()
        
        # Update report statistics
        self.report.execution_count += 1
        self.report.last_execution_status = 'completed'
        self.report.last_run = self.completed_at
        
        # Update average execution time
        if self.report.average_execution_time:
            avg = self.report.average_execution_time
            new_avg = (avg * (self.report.execution_count - 1) + self.execution_time) / self.report.execution_count
            self.report.average_execution_time = new_avg
        else:
            self.report.average_execution_time = self.execution_time
        
        self.report.save()
    
    def mark_as_failed(self, error_message, stack_trace=None):
        """Mark execution as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        
        if stack_trace:
            self.stack_trace = stack_trace
        
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.execution_time = Decimal(str(duration))
        
        self.save()
        
        # Update report statistics
        self.report.last_execution_status = 'failed'
        self.report.save(update_fields=['last_execution_status'])


# ============================================================================
# REPORT WIDGET MODEL
# ============================================================================

class ReportWidget(models.Model):
    """
    Dashboard widgets for quick insights
    """
    
    WIDGET_TYPE_CHOICES = [
        ('metric', 'Metric Card'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('list', 'List'),
        ('gauge', 'Gauge'),
        ('trend', 'Trend Line'),
    ]
    
    CHART_TYPE_CHOICES = [
        ('bar', 'Bar Chart'),
        ('line', 'Line Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Widget Configuration
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPE_CHOICES,
        blank=True
    )
    
    # Data Source
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='widgets'
    )
    data_source = models.CharField(
        max_length=100,
        help_text="Model or data source"
    )
    query_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Query configuration"
    )
    
    # Display Settings
    refresh_interval = models.IntegerField(
        default=300,
        help_text="Refresh interval in seconds"
    )
    width = models.IntegerField(default=6, validators=[MinValueValidator(1), MaxValueValidator(12)])
    height = models.IntegerField(default=300)
    order = models.IntegerField(default=0)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    allowed_users = models.ManyToManyField(User, related_name='accessible_widgets', blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_widgets'
    )
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Report Widget'
        verbose_name_plural = 'Report Widgets'
    
    def __str__(self):
        return self.name


# ============================================================================
# SAVED REPORT MODEL
# ============================================================================

class SavedReport(models.Model):
    """
    User's saved/favorited reports
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_reports'
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='saved_by_users'
    )
    
    # Custom Settings
    custom_name = models.CharField(max_length=255, blank=True)
    custom_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="User's custom parameters"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'report']
        ordering = ['-last_accessed']
        verbose_name = 'Saved Report'
        verbose_name_plural = 'Saved Reports'
    
    def __str__(self):
        return f"{self.user.username} - {self.custom_name or self.report.name}"