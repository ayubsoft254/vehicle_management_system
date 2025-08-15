from django.db import models
from core.models import User
import uuid

class ReportTemplate(models.Model):
    """Predefined report templates"""
    
    REPORT_TYPES = [
        ('sales', 'Sales Report'),
        ('payments', 'Payment Report'),
        ('defaulters', 'Defaulters Report'),
        ('vehicle_status', 'Vehicle Status Report'),
        ('payroll', 'Payroll Report'),
        ('expenses', 'Expense Report'),
        ('auction', 'Auction Report'),
        ('vehicle_costing', 'Vehicle Cost Analysis'),
        ('multi_company', 'Multi-Company Breakdown'),
        ('client_summary', 'Client Summary'),
        ('insurance', 'Insurance Report'),
        ('custom', 'Custom Report'),
    ]
    
    OUTPUT_FORMATS = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    
    # Query Configuration
    sql_query = models.TextField(blank=True, help_text="Custom SQL query for the report")
    filters = models.JSONField(blank=True, null=True, help_text="Available filters for the report")
    columns = models.JSONField(blank=True, null=True, help_text="Column configuration")
    
    # Output Settings
    default_format = models.CharField(max_length=10, choices=OUTPUT_FORMATS, default='pdf')
    include_charts = models.BooleanField(default=False)
    
    # Access Control
    allowed_roles = models.JSONField(
        default=list, 
        help_text="List of roles that can access this report"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class ReportGeneration(models.Model):
    """Track generated reports"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='generations')
    
    # Generation Details
    parameters = models.JSONField(blank=True, null=True, help_text="Parameters used for generation")
    output_format = models.CharField(max_length=10, choices=ReportTemplate.OUTPUT_FORMATS)
    
    # File Details
    file_path = models.FileField(upload_to='reports/', blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    
    # Status and Timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.template.name} - {self.created_at.date()}"
    
    @property
    def generation_time(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None