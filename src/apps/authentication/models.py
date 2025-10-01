"""
Authentication Models - Custom User Model with Roles
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator
from utils.constants import UserRole
from utils.validators import validate_phone_number


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user"""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        
        # Set default values for required fields if not provided
        extra_fields.setdefault('first_name', 'Admin')
        extra_fields.setdefault('last_name', 'User')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User Model with Role-Based Access Control
    Uses email for authentication instead of username
    """
    username = None  # Remove username field
    email = models.EmailField(
        'Email Address',
        unique=True,
        error_messages={
            'unique': 'A user with this email already exists.',
        }
    )
    
    # Personal Information
    first_name = models.CharField('First Name', max_length=150)
    last_name = models.CharField('Last Name', max_length=150)
    phone = models.CharField(
        'Phone Number',
        max_length=20,
        validators=[validate_phone_number],
        blank=True,
        help_text='Format: +254712345678 or 0712345678'
    )
    
    # Role and Status
    role = models.CharField(
        'User Role',
        max_length=20,
        choices=UserRole.CHOICES,
        default=UserRole.CLERK,
        help_text='User role determines access permissions'
    )
    
    # Profile Information
    profile_picture = models.ImageField(
        'Profile Picture',
        upload_to='profiles/',
        blank=True,
        null=True
    )
    address = models.TextField('Address', blank=True)
    city = models.CharField('City', max_length=100, blank=True)
    
    # Employment Information
    employee_id = models.CharField(
        'Employee ID',
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )
    department = models.CharField('Department', max_length=100, blank=True)
    hire_date = models.DateField('Hire Date', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField('Active Status', default=True)
    
    # Timestamps
    created_at = models.DateTimeField('Created At', auto_now_add=True)
    updated_at = models.DateTimeField('Updated At', auto_now=True)
    last_login = models.DateTimeField('Last Login', blank=True, null=True)
    
    # Custom manager
    objects = UserManager()
    
    # Use email as the unique identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the user's full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Return the user's first name"""
        return self.first_name
    
    def get_role_display_badge(self):
        """Return role with proper formatting for display"""
        role_colors = {
            UserRole.ADMIN: 'bg-red-100 text-red-800',
            UserRole.MANAGER: 'bg-purple-100 text-purple-800',
            UserRole.ACCOUNTANT: 'bg-green-100 text-green-800',
            UserRole.SALES: 'bg-blue-100 text-blue-800',
            UserRole.AUCTIONEER: 'bg-yellow-100 text-yellow-800',
            UserRole.CLERK: 'bg-gray-100 text-gray-800',
        }
        return role_colors.get(self.role, 'bg-gray-100 text-gray-800')
    
    def has_role(self, *roles):
        """Check if user has any of the specified roles"""
        return self.role in roles or self.is_superuser
    
    def can_access_module(self, module_name):
        """Check if user can access a specific module"""
        if self.is_superuser:
            return True
        
        try:
            from apps.permissions.models import RolePermission
            from utils.constants import AccessLevel
            
            permission = RolePermission.objects.get(
                role=self.role,
                module_name=module_name
            )
            return permission.access_level != AccessLevel.NO_ACCESS
        except:
            return False
    
    @property
    def initials(self):
        """Get user initials for avatar"""
        return f"{self.first_name[0]}{self.last_name[0]}".upper() if self.first_name and self.last_name else "?"


class UserProfile(models.Model):
    """
    Extended user profile information
    Separated for additional non-essential data
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Additional Information
    bio = models.TextField('Biography', blank=True)
    date_of_birth = models.DateField('Date of Birth', blank=True, null=True)
    national_id = models.CharField('National ID', max_length=20, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(
        'Emergency Contact Name',
        max_length=200,
        blank=True
    )
    emergency_contact_phone = models.CharField(
        'Emergency Contact Phone',
        max_length=20,
        blank=True,
        validators=[validate_phone_number]
    )
    emergency_contact_relationship = models.CharField(
        'Relationship',
        max_length=100,
        blank=True
    )
    
    # Preferences
    email_notifications = models.BooleanField(
        'Email Notifications',
        default=True,
        help_text='Receive email notifications'
    )
    sms_notifications = models.BooleanField(
        'SMS Notifications',
        default=True,
        help_text='Receive SMS notifications'
    )
    
    # Timestamps
    created_at = models.DateTimeField('Created At', auto_now_add=True)
    updated_at = models.DateTimeField('Updated At', auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile of {self.user.get_full_name()}"