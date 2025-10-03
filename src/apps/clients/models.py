"""
Clients Models
Manage customer/client information and vehicle purchases
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from utils.constants import ClientStatus, DocumentType
from utils.validators import (
    validate_phone_number, 
    validate_passport_number
)
import os


class ClientManager(models.Manager):
    """Custom manager for Client model"""
    
    def active(self):
        """Get all active clients"""
        return self.filter(status=ClientStatus.ACTIVE)
    
    def inactive(self):
        """Get all inactive clients"""
        return self.filter(status=ClientStatus.INACTIVE)
    
    def defaulted(self):
        """Get all defaulted clients"""
        return self.filter(status=ClientStatus.DEFAULTED)
    
    def completed(self):
        """Get clients who completed payments"""
        return self.filter(status=ClientStatus.COMPLETED)


class Client(models.Model):
    """
    Main client/customer model
    Stores personal and contact information
    """
    
    # Personal Information
    first_name = models.CharField(
        'First Name',
        max_length=100
    )
    
    last_name = models.CharField(
        'Last Name',
        max_length=100
    )
    
    other_names = models.CharField(
        'Other Names',
        max_length=100,
        blank=True,
        help_text='Middle name or additional names'
    )
    
    date_of_birth = models.DateField(
        'Date of Birth',
        blank=True,
        null=True
    )
    
    gender = models.CharField(
        'Gender',
        max_length=10,
        choices=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        blank=True
    )
    
    # Identification
    id_type = models.CharField(
        'ID Type',
        max_length=20,
        choices=[
            ('national_id', 'National ID'),
            ('passport', 'Passport'),
            ('other', 'Other'),
        ],
        default='national_id'
    )
    
    id_number = models.CharField(
        'ID/Passport Number',
        max_length=50,
        unique=True,
        help_text='National ID or Passport number'
    )
    
    # Contact Information
    phone_primary = models.CharField(
        'Primary Phone',
        max_length=20,
        validators=[validate_phone_number],
        help_text='Format: +254712345678 or 0712345678'
    )
    
    phone_secondary = models.CharField(
        'Secondary Phone',
        max_length=20,
        validators=[validate_phone_number],
        blank=True,
        help_text='Alternative phone number'
    )
    
    email = models.EmailField(
        'Email Address',
        blank=True,
        help_text='Client email address'
    )
    
    # Address Information
    physical_address = models.TextField(
        'Physical Address',
        help_text='Current residential address'
    )
    
    city = models.CharField(
        'City/Town',
        max_length=100,
        blank=True
    )
    
    county = models.CharField(
        'County',
        max_length=100,
        blank=True
    )
    
    postal_address = models.CharField(
        'Postal Address',
        max_length=200,
        blank=True
    )
    
    # Employment/Income Information
    occupation = models.CharField(
        'Occupation',
        max_length=200,
        blank=True
    )
    
    employer = models.CharField(
        'Employer',
        max_length=200,
        blank=True
    )
    
    monthly_income = models.DecimalField(
        'Monthly Income',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text='Estimated monthly income'
    )
    
    # Next of Kin
    next_of_kin_name = models.CharField(
        'Next of Kin Name',
        max_length=200,
        blank=True
    )
    
    next_of_kin_phone = models.CharField(
        'Next of Kin Phone',
        max_length=20,
        validators=[validate_phone_number],
        blank=True
    )
    
    next_of_kin_relationship = models.CharField(
        'Relationship',
        max_length=100,
        blank=True,
        help_text='Relationship to next of kin'
    )
    
    next_of_kin_address = models.TextField(
        'Next of Kin Address',
        blank=True
    )
    
    # Financial Information
    credit_limit = models.DecimalField(
        'Credit Limit',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Maximum credit allowed for this client'
    )
    
    current_debt = models.DecimalField(
        'Current Debt',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Total outstanding debt'
    )
    
    # Status
    status = models.CharField(
        'Status',
        max_length=20,
        choices=ClientStatus.CHOICES,
        default=ClientStatus.ACTIVE,
        db_index=True
    )
    
    is_active = models.BooleanField(
        'Active',
        default=True,
        help_text='Whether client account is active'
    )
    
    is_blacklisted = models.BooleanField(
        'Blacklisted',
        default=False,
        help_text='Client is blacklisted due to default or fraud'
    )
    
    blacklist_reason = models.TextField(
        'Blacklist Reason',
        blank=True,
        help_text='Reason for blacklisting'
    )
    
    # Additional Information
    notes = models.TextField(
        'Notes',
        blank=True,
        help_text='Additional notes about the client'
    )
    
    profile_photo = models.ImageField(
        'Profile Photo',
        upload_to='clients/photos/',
        blank=True,
        null=True
    )
    
    # Metadata
    registered_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='clients_registered'
    )
    
    date_registered = models.DateTimeField(
        'Date Registered',
        auto_now_add=True
    )
    
    last_updated = models.DateTimeField(
        'Last Updated',
        auto_now=True
    )
    
    # Custom manager
    objects = ClientManager()
    
    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-date_registered']
        indexes = [
            models.Index(fields=['status', '-date_registered']),
            models.Index(fields=['id_number']),
            models.Index(fields=['phone_primary']),
            models.Index(fields=['is_active', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.id_number}"
    
    def get_full_name(self):
        """Get client's full name"""
        names = [self.first_name]
        if self.other_names:
            names.append(self.other_names)
        names.append(self.last_name)
        return ' '.join(names)
    
    @property
    def available_credit(self):
        """Calculate available credit"""
        return self.credit_limit - self.current_debt
    
    @property
    def credit_utilization(self):
        """Calculate credit utilization percentage"""
        if self.credit_limit > 0:
            return (self.current_debt / self.credit_limit) * 100
        return 0
    
    @property
    def initials(self):
        """Get client initials"""
        return f"{self.first_name[0]}{self.last_name[0]}".upper()
    
    def get_status_color(self):
        """Get color for status badge"""
        color_map = {
            ClientStatus.ACTIVE: 'green',
            ClientStatus.INACTIVE: 'gray',
            ClientStatus.DEFAULTED: 'red',
            ClientStatus.COMPLETED: 'blue',
        }
        return color_map.get(self.status, 'gray')
    
    def has_active_vehicle(self):
        """Check if client has any active vehicle purchase"""
        return self.vehicles.filter(
            is_active=True,
            vehicle__status='sold'
        ).exists()
    
    def total_purchases(self):
        """Get total number of vehicle purchases"""
        return self.vehicles.count()
    
    def total_amount_paid(self):
        """Calculate total amount paid by client"""
        from apps.payments.models import Payment
        return Payment.objects.filter(
            client=self
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')


class ClientVehicle(models.Model):
    """
    Link clients to vehicles they purchased
    Tracks purchase details and payment status
    """
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.PROTECT,
        related_name='client_purchases'
    )
    
    # Purchase Details
    purchase_date = models.DateField(
        'Purchase Date',
        help_text='Date vehicle was purchased/assigned'
    )
    
    purchase_price = models.DecimalField(
        'Purchase Price',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Agreed purchase price'
    )
    
    deposit_paid = models.DecimalField(
        'Deposit Paid',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00')
    )
    
    total_paid = models.DecimalField(
        'Total Paid',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Total amount paid so far'
    )
    
    balance = models.DecimalField(
        'Balance',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Remaining balance'
    )
    
    # Payment Plan
    monthly_installment = models.DecimalField(
        'Monthly Installment',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text='Monthly payment amount'
    )
    
    installment_months = models.IntegerField(
        'Installment Period (Months)',
        validators=[MinValueValidator(1)],
        blank=True,
        null=True,
        help_text='Number of months for payment'
    )
    
    interest_rate = models.DecimalField(
        'Interest Rate (%)',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Annual interest rate'
    )
    
    # Status
    is_active = models.BooleanField(
        'Active',
        default=True,
        help_text='Whether this purchase is active'
    )
    
    is_paid_off = models.BooleanField(
        'Paid Off',
        default=False,
        help_text='Whether vehicle is fully paid'
    )
    
    date_paid_off = models.DateField(
        'Date Paid Off',
        blank=True,
        null=True
    )
    
    # Notes
    notes = models.TextField(
        'Notes',
        blank=True,
        help_text='Additional notes about this purchase'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='client_vehicle_assignments'
    )
    
    created_at = models.DateTimeField(
        'Created At',
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        'Updated At',
        auto_now=True
    )
    
    class Meta:
        db_table = 'client_vehicles'
        verbose_name = 'Client Vehicle'
        verbose_name_plural = 'Client Vehicles'
        ordering = ['-purchase_date']
        unique_together = ['client', 'vehicle']
    
    def __str__(self):
        return f"{self.client.get_full_name()} - {self.vehicle.full_name}"
    
    @property
    def payment_progress(self):
        """Calculate payment progress percentage"""
        if self.purchase_price > 0:
            return (self.total_paid / self.purchase_price) * 100
        return 0
    
    def update_balance(self):
        """Update balance based on payments"""
        self.balance = self.purchase_price - self.total_paid
        if self.balance <= 0:
            self.is_paid_off = True
            if not self.date_paid_off:
                from django.utils import timezone
                self.date_paid_off = timezone.now().date()
        self.save()


class ClientDocument(models.Model):
    """
    Store client documents
    ID copies, agreements, contracts, etc.
    """
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document_type = models.CharField(
        'Document Type',
        max_length=50,
        choices=DocumentType.CHOICES,
        help_text='Type of document'
    )
    
    title = models.CharField(
        'Document Title',
        max_length=200,
        help_text='Descriptive title for the document'
    )
    
    file = models.FileField(
        'File',
        upload_to='clients/documents/%Y/%m/',
        help_text='Upload document file'
    )
    
    description = models.TextField(
        'Description',
        blank=True,
        help_text='Additional details about the document'
    )
    
    # Metadata
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='client_documents_uploaded'
    )
    
    uploaded_at = models.DateTimeField(
        'Uploaded At',
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'client_documents'
        verbose_name = 'Client Document'
        verbose_name_plural = 'Client Documents'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} - {self.client.get_full_name()}"
    
    def delete(self, *args, **kwargs):
        """Delete the file when document is deleted"""
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)
    
    @property
    def file_size(self):
        """Get file size in human-readable format"""
        if self.file:
            size = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return "0 B"
    
    @property
    def file_extension(self):
        """Get file extension"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ""