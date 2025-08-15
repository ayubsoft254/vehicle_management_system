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
class MiscellaneousFinancial(models.Model):
    """Handle miscellaneous financials like discounts, after-sale expenses, etc."""
    
    FINANCIAL_TYPES = [
        ('discount', 'Discount'),
        ('after_sale_repair', 'After-Sale Repair'),
        ('after_sale_service', 'After-Sale Service'),
        ('promotional_expense', 'Promotional Expense'),
        ('warranty_claim', 'Warranty Claim'),
        ('refund', 'Refund'),
        ('adjustment', 'Financial Adjustment'),
        ('commission', 'Sales Commission'),
        ('incentive', 'Sales Incentive'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    financial_type = models.CharField(max_length=30, choices=FINANCIAL_TYPES)
    
    # Amount (can be positive or negative)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Related Objects
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, blank=True, null=True)
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, blank=True, null=True)
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, blank=True, null=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='misc_financials')
    
    # Dates
    transaction_date = models.DateField()
    effective_date = models.DateField()
    
    # Approval and Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approval_required = models.BooleanField(default=True)
    
    # Documentation
    reference_number = models.CharField(max_length=50, blank=True)
    supporting_document = models.FileField(upload_to='misc_financials/', blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_misc_financials')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_misc_financials')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date']
        verbose_name = "Miscellaneous Financial"
        verbose_name_plural = "Miscellaneous Financials"
    
    def __str__(self):
        return f"{self.title} - {self.amount}"

class WarrantyTracking(models.Model):
    """Track warranty claims and coverage for vehicles"""
    
    WARRANTY_TYPES = [
        ('manufacturer', 'Manufacturer Warranty'),
        ('dealer', 'Dealer Warranty'),
        ('extended', 'Extended Warranty'),
        ('parts', 'Parts Warranty'),
        ('service', 'Service Warranty'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('claimed', 'Claimed'),
        ('void', 'Void'),
    ]
    
    CLAIM_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='warranties')
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='warranties')
    
    # Warranty Details
    warranty_type = models.CharField(max_length=20, choices=WARRANTY_TYPES)
    warranty_provider = models.CharField(max_length=100)
    warranty_number = models.CharField(max_length=50, unique=True)
    
    # Coverage
    coverage_description = models.TextField()
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Mileage Coverage (if applicable)
    mileage_limit = models.PositiveIntegerField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Claim Information (if claimed)
    claim_date = models.DateField(blank=True, null=True)
    claim_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    claim_description = models.TextField(blank=True)
    claim_status = models.CharField(max_length=20, choices=CLAIM_STATUS, blank=True)
    
    # Documentation
    warranty_document = models.FileField(upload_to='warranties/', blank=True, null=True)
    claim_documents = models.FileField(upload_to='warranty_claims/', blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Warranty Tracking"
    
    def __str__(self):
        return f"{self.vehicle} - {self.warranty_type}"
    
    @property
    def is_active(self):
        from django.utils import timezone
        return (
            self.status == 'active' and 
            self.start_date <= timezone.now().date() <= self.end_date
        )
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.status == 'active':
            delta = self.end_date - timezone.now().date()
            return max(0, delta.days)
        return 0