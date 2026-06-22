"""
Clients Models
Manage customer/client information and vehicle purchases
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from utils.constants import ClientStatus, DocumentType
from utils.validators import validate_passport_number
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
    
    # Link to User Account
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_profile',
        help_text='Linked user account for client portal access'
    )
    
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
    
    kra_pin = models.CharField(
        'KRA PIN',
        max_length=20,
        blank=True,
        null=True,
        help_text='Kenya Revenue Authority Personal Identification Number'
    )
    
    # Contact Information
    phone_primary = models.CharField(
        'Primary Phone',
        max_length=20,
        help_text='International or local format accepted'
    )
    
    phone_secondary = models.CharField(
        'Secondary Phone',
        max_length=20,
        blank=True,
        help_text='Alternative phone number (optional)'
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

    client_purchase_price = models.DecimalField(
        'Client Purchase Price',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Auto-calculated client purchase price before manual adjustments'
    )

    final_selling_price = models.DecimalField(
        'Final Selling Price',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Editable selling price before deducting extra costs'
    )

    extra_costs_total = models.DecimalField(
        'Extra Costs Total',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Total extra costs deducted from final selling price'
    )

    extra_costs_json = models.TextField(
        'Extra Costs JSON',
        blank=True,
        default='[]',
        help_text='JSON list of extra costs with description and amount'
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
    
    # Payment Type & Flexibility
    PAYMENT_TYPE_CHOICES = [
        ('full', 'Pay in Full'),
        ('installment', 'Monthly Installments'),
        ('flexible', 'Flexible (Monthly or Weekly)'),
    ]
    
    payment_type = models.CharField(
        'Payment Type',
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='installment',
        help_text='How the client will pay for the vehicle'
    )
    
    remainder_payment_type = models.CharField(
        'Remainder Payment Type',
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('weekly', 'Weekly'),
        ],
        default='monthly',
        blank=True,
        null=True,
        help_text='Whether remainder is paid monthly or weekly'
    )
    
    monthly_payment_date = models.IntegerField(
        'Monthly Payment Date',
        default=12,
        validators=[MinValueValidator(1)],
        blank=True,
        null=True,
        help_text='Day of month for monthly payments (1-31, e.g., 12 for 12th of month)'
    )
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    weekly_payment_day = models.IntegerField(
        'Weekly Payment Day',
        choices=WEEKDAY_CHOICES,
        default=2,
        blank=True,
        null=True,
        help_text='Day of week for weekly payments (0=Monday, 6=Sunday)'
    )
    
    allow_flexible_payments = models.BooleanField(
        'Allow Flexible Payments',
        default=False,
        help_text='Allow client to make payments at any time, with flexible scheduling'
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
    
    other_payment_details = models.TextField(
        'Other Payment Details',
        blank=True,
        help_text='Optional payment details to include in the agreement'
    )
    
    # Broker ledger link
    broker = models.ForeignKey(
        'vehicles.Broker',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        help_text='Broker linked to this sale (for ledger tracking)'
    )

    BROKER_COMMISSION_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    broker_commission_status = models.CharField(
        'Commission Status',
        max_length=10,
        choices=BROKER_COMMISSION_STATUS_CHOICES,
        default='unpaid',
        help_text='Whether the broker commission for this sale has been paid'
    )

    # Commission & Sales
    broker_name = models.CharField(
        'Broker Name',
        max_length=200,
        blank=True,
        null=True,
        help_text='Name of the broker handling this transaction'
    )
    
    broker_id_no = models.CharField(
        'Broker ID Number',
        max_length=50,
        blank=True,
        null=True,
        help_text='Broker identification number'
    )
    
    broker_phone_no = models.CharField(
        'Broker Phone Number',
        max_length=20,
        blank=True,
        null=True,
        help_text='Broker contact phone number'
    )
    
    commission_amount = models.DecimalField(
        'Commission Amount',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Commission amount for the broker'
    )
    
    commission_percentage = models.DecimalField(
        'Commission Percentage',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Commission percentage (e.g., 5.00 for 5%)'
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


class TrackerCompany(models.Model):
    """Master data for tracker provider/vendor names and optional contact details."""

    name = models.CharField(
        max_length=200,
        unique=True,
        help_text='Tracker company/vendor name'
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text='Primary contact phone (optional)'
    )

    email = models.EmailField(
        blank=True,
        null=True,
        help_text='Contact email (optional)'
    )

    contact_person = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text='Contact person name (optional)'
    )

    notes = models.TextField(
        blank=True,
        null=True,
        help_text='Additional notes (optional)'
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Whether this tracker company is active'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tracker_companies'
        ordering = ['name']
        verbose_name = 'Tracker Company'
        verbose_name_plural = 'Tracker Companies'

    def __str__(self):
        return self.name


# ==================== VEHICLE TRACKER MODEL ====================

class VehicleTracker(models.Model):
    """
    Track one or more GPS/vehicle trackers installed on a client's vehicle.
    Each tracker has its own buying & selling price and optional payment plan.
    """

    client_vehicle = models.ForeignKey(
        ClientVehicle,
        on_delete=models.CASCADE,
        related_name='trackers',
        help_text='Vehicle purchase this tracker is linked to'
    )

    tracker_name = models.CharField(
        'Tracker Name / Model',
        max_length=200,
        help_text='e.g. Teltonika FMB920'
    )

    serial_number = models.CharField(
        'Serial Number / IMEI',
        max_length=100,
        blank=True,
        help_text='Device serial number or IMEI'
    )

    certificate_number = models.CharField(
        'Certificate Number',
        max_length=100,
        blank=True,
        help_text='Tracker certificate number (if available)'
    )

    provider = models.CharField(
        'Provider / Vendor',
        max_length=200,
        blank=True,
        help_text='Company or person supplying the tracker'
    )

    buying_price = models.DecimalField(
        'Buying Price (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount dealer paid for this tracker'
    )

    selling_price = models.DecimalField(
        'Selling Price (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount client is charged for this tracker'
    )

    # Payment plan fields
    TRACKER_PAYMENT_TYPE_CHOICES = [
        ('full', 'Full Payment'),
        ('flexible', 'Flexible Installments'),
        ('deduct_from_deposit', 'Deduct from Deposit'),
    ]

    TRACKER_PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('other', 'Other'),
    ]

    payment_type = models.CharField(
        'Payment Type',
        max_length=30,
        choices=TRACKER_PAYMENT_TYPE_CHOICES,
        default='full',
        help_text='How the client pays for this tracker',
    )

    payment_method = models.CharField(
        'Payment Method',
        max_length=30,
        choices=TRACKER_PAYMENT_METHOD_CHOICES,
        default='cash',
        help_text='Method used to pay for this tracker',
    )

    installments_json = models.TextField(
        'Installments Schedule (JSON)',
        blank=True,
        default='[]',
        help_text='JSON array of {due_date, amount} installment schedule entries',
    )

    has_payment_plan = models.BooleanField(
        'Has Payment Plan',
        default=False,
        help_text='Whether client pays for this tracker in installments'
    )

    deposit = models.DecimalField(
        'Deposit (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
    )

    installment_months = models.PositiveIntegerField(
        'Installment Months',
        null=True,
        blank=True,
    )

    interest_rate = models.DecimalField(
        'Interest Rate (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Annual interest rate for payment plan (%)',
        blank=True,
    )

    monthly_installment = models.DecimalField(
        'Monthly Installment (KES)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    total_paid = models.DecimalField(
        'Total Paid (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    balance = models.DecimalField(
        'Balance (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    installed_date = models.DateField(
        'Installation Date',
        null=True,
        blank=True,
    )

    notes = models.TextField(
        'Notes',
        blank=True,
    )

    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='trackers_added',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicle_trackers'
        verbose_name = 'Vehicle Tracker'
        verbose_name_plural = 'Vehicle Trackers'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.tracker_name} — {self.client_vehicle}"

    def save(self, *args, **kwargs):
        # Auto-compute balance
        self.balance = self.selling_price - self.total_paid
        
        # Auto-calculate monthly installment if payment plan is enabled
        if self.has_payment_plan and self.deposit is not None and \
           self.installment_months and self.selling_price:
            
            balance_after_deposit = self.selling_price - self.deposit
            
            # Calculate monthly installment (no interest)
            if self.installment_months and balance_after_deposit:
                self.monthly_installment = round(
                    balance_after_deposit / Decimal(str(self.installment_months)),
                    2
                )
        
        super().save(*args, **kwargs)

    @property
    def profit(self):
        return self.selling_price - self.buying_price


# ==================== VEHICLE SALE WITNESS MODEL ====================

class VehicleSaleWitness(models.Model):
    """
    Broker / witness present at the time of vehicle sale.
    A sale can have 1 or 2 witnesses.
    """

    ROLE_CHOICES = [
        ('broker', 'Broker'),
        ('witness', 'Witness'),
        ('other', 'Other'),
    ]

    client_vehicle = models.ForeignKey(
        ClientVehicle,
        on_delete=models.CASCADE,
        related_name='witnesses',
        help_text='Vehicle sale this witness is linked to'
    )

    role = models.CharField(
        'Role',
        max_length=20,
        choices=ROLE_CHOICES,
        default='witness',
    )

    full_name = models.CharField(
        'Full Name',
        max_length=200,
    )

    id_number = models.CharField(
        'ID / Passport Number',
        max_length=50,
        blank=True,
    )

    phone = models.CharField(
        'Phone Number',
        max_length=30,
        blank=True,
    )

    notes = models.TextField(
        'Notes',
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicle_sale_witnesses'
        verbose_name = 'Sale Witness / Broker'
        verbose_name_plural = 'Sale Witnesses / Brokers'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_role_display()}: {self.full_name}"


# ==================== AGREEMENT SIGNATURE MODEL ====================

class AgreementSignature(models.Model):
    """
    Stores an online e-signature for a sales agreement.
    The signature is captured via a canvas pad and saved as a base-64 PNG.
    """

    client_vehicle = models.OneToOneField(
        ClientVehicle,
        on_delete=models.CASCADE,
        related_name='agreement_signature',
        help_text='The vehicle purchase this signature belongs to',
    )

    # Signer identity (pre-filled from client, editable on the sign page)
    signer_name = models.CharField(
        'Signer Full Name',
        max_length=200,
        help_text='Name of the person who signed',
    )

    signer_id_number = models.CharField(
        'Signer ID / Passport',
        max_length=50,
        blank=True,
        help_text='National ID or passport used to verify identity',
    )

    witness_name = models.CharField(
        'Witness Full Name',
        max_length=200,
        blank=True,
        help_text='Witness name if a witness signs online',
    )

    witness_id_number = models.CharField(
        'Witness ID / Passport',
        max_length=50,
        blank=True,
        help_text='Witness ID or passport number',
    )

    witness_phone = models.CharField(
        'Witness Phone / Mobile',
        max_length=20,
        blank=True,
        help_text='Witness phone or mobile number',
    )

    seller_name = models.CharField(
        'Seller Full Name',
        max_length=200,
        blank=True,
        help_text='Hoza representative signing the agreement',
    )

    # Signature image stored as a data-URL (data:image/png;base64,...)
    signature_data = models.TextField(
        'Signature Image Data',
        help_text='Base-64 encoded PNG of the drawn signature',
    )

    witness_signature_data = models.TextField(
        'Witness Signature Image Data',
        blank=True,
        default='',
        help_text='Base-64 encoded PNG of the witness signature',
    )

    seller_signature_data = models.TextField(
        'Seller Signature Image Data',
        blank=True,
        default='',
        help_text='Base-64 encoded PNG of the seller signature',
    )

    # Audit
    ip_address = models.GenericIPAddressField(
        'IP Address',
        blank=True,
        null=True,
        help_text='IP address from which the signature was submitted',
    )

    signed_at = models.DateTimeField(
        'Signed At',
        auto_now_add=True,
    )

    signed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agreements_signed',
        help_text='Logged-in user who submitted the signature (if any)',
    )

    class Meta:
        db_table = 'agreement_signatures'
        verbose_name = 'Agreement Signature'
        verbose_name_plural = 'Agreement Signatures'

    def __str__(self):
        return f"Signature: {self.signer_name} — {self.client_vehicle}"
