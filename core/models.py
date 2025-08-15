from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid

class User(AbstractUser):
    """Extended User model with additional fields and role-based access"""
    
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('sales', 'Sales Representative'),
        ('accountant', 'Accountant'),
        ('auctioneer', 'Auctioneer'),
        ('manager', 'Manager'),
        ('clerk', 'Clerk'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = PhoneNumberField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='clerk')
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    department = models.CharField(max_length=50, blank=True)
    hire_date = models.DateField(blank=True, null=True)
    is_active_employee = models.BooleanField(default=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    def has_role(self, role):
        """Check if user has specific role"""
        return self.role == role
    
    def has_any_role(self, roles):
        """Check if user has any of the specified roles"""
        return self.role in roles

class RolePermission(models.Model):
    """Define module-level permissions for each role"""
    
    MODULE_CHOICES = [
        ('dashboard', 'Dashboard'),
        ('vehicles', 'Vehicle Management'),
        ('clients', 'Client Management'),
        ('payments', 'Payment Management'),
        ('payroll', 'Payroll Management'),
        ('expenses', 'Expense Tracking'),
        ('auctions', 'Auction Management'),
        ('insurance', 'Insurance Management'),
        ('notifications', 'Notifications'),
        ('documents', 'Document Management'),
        ('reports', 'Reports'),
        ('audit', 'Audit Logs'),
    ]
    
    ACCESS_LEVELS = [
        ('none', 'No Access'),
        ('read', 'Read Only'),
        ('write', 'Read & Write'),
        ('full', 'Full Access'),
    ]
    
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES)
    module_name = models.CharField(max_length=50, choices=MODULE_CHOICES)
    access_level = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('role', 'module_name')
    
    def __str__(self):
        return f"{self.role} - {self.module_name}: {self.access_level}"

class Company(models.Model):
    """Multi-company support for vehicle inventory"""
    
    name = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    phone = PhoneNumberField()
    email = models.EmailField()
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Companies"
    
    def __str__(self):
        return self.name