from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    """
    Tenant model for multi-tenancy support.
    Each client (company) gets their own schema/database.
    """
    name = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    
    # Company-specific settings
    company_name = models.CharField(max_length=255)
    company_email = models.EmailField()
    company_phone = models.CharField(max_length=20)
    company_address = models.TextField(blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    
    # Theme customization
    primary_color = models.CharField(max_length=7, default='#3B82F6')  # Tailwind blue-500
    secondary_color = models.CharField(max_length=7, default='#10B981')  # Tailwind green-500
    
    # Subscription/Payment (for future use)
    is_active = models.BooleanField(default=True)
    subscription_end_date = models.DateField(blank=True, null=True)
    
    auto_create_schema = True
    
    class Meta:
        db_table = 'clients'
    
    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """
    Domain model for mapping domains to tenants.
    """
    pass


class User(AbstractUser):
    """
    Custom User model with role-based access control.
    """
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('sales', 'Sales Manager'),
        ('accountant', 'Accountant'),
        ('auctioneer', 'Auctioneer'),
        ('manager', 'General Manager'),
        ('staff', 'Staff'),
    ]
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Employment details
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField(blank=True, null=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Status
    is_active_employee = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    def get_role_display_name(self):
        return dict(self.ROLE_CHOICES).get(self.role, 'Unknown')


class RolePermission(models.Model):
    """
    Dynamic role-based permissions for modules.
    """
    ACCESS_LEVELS = [
        ('none', 'No Access'),
        ('view', 'View Only'),
        ('edit', 'View & Edit'),
        ('full', 'Full Access'),
    ]
    
    MODULES = [
        ('dashboard', 'Dashboard'),
        ('vehicles', 'Vehicle Inventory'),
        ('clients', 'Client Management'),
        ('payments', 'Payment Module'),
        ('payroll', 'Payroll Management'),
        ('expenses', 'Expense Tracking'),
        ('repossessions', 'Repossessed Cars'),
        ('auctions', 'Auction Management'),
        ('insurance', 'Insurance Management'),
        ('notifications', 'Notifications'),
        ('documents', 'Document Manager'),
        ('reports', 'Reporting'),
        ('audit', 'Audit Logs'),
        ('settings', 'System Settings'),
    ]
    
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES)
    module_name = models.CharField(max_length=50, choices=MODULES)
    access_level = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'role_permissions'
        unique_together = ['role', 'module_name']
        ordering = ['role', 'module_name']
    
    def __str__(self):
        return f"{self.get_role_display()} - {self.get_module_name_display()}: {self.get_access_level_display()}"


class SystemSettings(models.Model):
    """
    Global system settings per tenant.
    """
    # Interest & Financial Settings
    default_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00,
        help_text="Default annual interest rate for installments (%)"
    )
    
    late_payment_penalty = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=2.00,
        help_text="Late payment penalty (%)"
    )
    
    # Notification Settings
    payment_reminder_days = models.IntegerField(
        default=3,
        help_text="Days before payment due to send reminder"
    )
    
    insurance_expiry_days = models.IntegerField(
        default=30,
        help_text="Days before insurance expiry to send reminder"
    )
    
    # Document Settings
    max_document_size_mb = models.IntegerField(
        default=10,
        help_text="Maximum document upload size in MB"
    )
    
    # Currency
    currency_symbol = models.CharField(max_length=10, default='KSH')
    currency_code = models.CharField(max_length=3, default='KES')
    
    # Business Hours
    business_start_time = models.TimeField(default='08:00:00')
    business_end_time = models.TimeField(default='17:00:00')
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'system_settings'
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return "System Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create system settings."""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings