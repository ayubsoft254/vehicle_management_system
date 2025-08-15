from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
import uuid
from vehicles.models import Vehicle
from clients.models import Client
from core.models import User


class InsuranceProvider(models.Model):
    """Insurance company/provider information"""
    
    name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = PhoneNumberField()
    email = models.EmailField()
    address = models.TextField()
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Insurance(models.Model):
    """Vehicle insurance records"""
    
    INSURANCE_TYPES = [
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('fire_theft', 'Fire & Theft'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending Renewal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='insurances')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='insurances')
    provider = models.ForeignKey(InsuranceProvider, on_delete=models.CASCADE)
    
    # Policy Details
    policy_number = models.CharField(max_length=50, unique=True)
    insurance_type = models.CharField(max_length=20, choices=INSURANCE_TYPES)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.vehicle} - {self.policy_number}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return self.end_date < timezone.now().date()
    
    @property
    def days_to_expiry(self):
        from django.utils import timezone
        delta = self.end_date - timezone.now().date()
        return delta.days
