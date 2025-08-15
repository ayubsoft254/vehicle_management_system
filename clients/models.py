from django.db import models
from core.models import User
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Client(models.Model):
    """Client/Customer model with comprehensive information"""
    
    CLIENT_TYPES = [
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
    ]
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    ID_TYPES = [
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPES, default='individual')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    company_name = models.CharField(max_length=100, blank=True)  # For corporate clients
    
    # Contact Information
    email = models.EmailField(unique=True)
    phone = PhoneNumberField()
    alternative_phone = PhoneNumberField(blank=True, null=True)
    
    # Personal Details
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    
    # Identification
    id_type = models.CharField(max_length=20, choices=ID_TYPES)
    id_number = models.CharField(max_length=20, unique=True)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=50)
    county = models.CharField(max_length=50, default='Mombasa')
    postal_code = models.CharField(max_length=10, blank=True)
    
    # Financial Information
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_score = models.PositiveIntegerField(blank=True, null=True, 
                                               validators=[MinValueValidator(300), MaxValueValidator(850)])
    
    # Employment/Business Information
    employer_name = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=50, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    years_employed = models.PositiveIntegerField(blank=True, null=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True)
    
    # Status and Notes
    is_active = models.BooleanField(default=True)
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Metadata
    registered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='registered_clients')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.client_type == 'corporate':
            return f"{self.company_name} ({self.first_name} {self.last_name})"
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        return self.company_name if self.company_name else self.full_name