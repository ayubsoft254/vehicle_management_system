from django.db import models
from core.models import User
import uuid

class DocumentCategory(models.Model):
    """Categories for organizing documents"""
    
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Document Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Document(models.Model):
    """Document management for clients, vehicles, and general business"""
    
    DOCUMENT_TYPES = [
        ('contract', 'Sales Contract'),
        ('agreement', 'Payment Agreement'),
        ('logbook', 'Vehicle Logbook'),
        ('insurance', 'Insurance Document'),
        ('id_copy', 'ID Copy'),
        ('passport_copy', 'Passport Copy'),
        ('license', 'Driving License'),
        ('proof_income', 'Proof of Income'),
        ('bank_statement', 'Bank Statement'),
        ('receipt', 'Payment Receipt'),
        ('invoice', 'Invoice'),
        ('valuation', 'Vehicle Valuation'),
        ('inspection', 'Inspection Report'),
        ('other', 'Other'),
    ]
    
    ACCESS_LEVELS = [
        ('public', 'Public'),
        ('internal', 'Internal Only'),
        ('restricted', 'Restricted'),
        ('confidential', 'Confidential'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # File Information
    file = models.FileField(upload_to='documents/')
    file_size = models.PositiveIntegerField(blank=True, null=True)  # in bytes
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Relations (optional - documents can be related to clients, vehicles, etc.)
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, blank=True, null=True, related_name='documents')
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, blank=True, null=True, related_name='documents')
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, blank=True, null=True, related_name='documents')
    
    # Security and Access
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVELS, default='internal')
    password_protected = models.BooleanField(default=False)
    
    # Document Properties
    document_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    version = models.CharField(max_length=10, default='1.0')
    is_signed = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def file_extension(self):
        return self.file.name.split('.')[-1].upper() if self.file else ''
    
    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()