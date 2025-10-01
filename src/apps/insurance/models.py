"""
Models for the insurance app
Handles insurance providers, policies, claims, and payments
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

User = get_user_model()


# ==================== CUSTOM MANAGERS ====================

class InsurancePolicyManager(models.Manager):
    """Custom manager for InsurancePolicy model"""
    
    def active(self):
        """Get active insurance policies"""
        today = timezone.now().date()
        return self.filter(
            status='active',
            end_date__gte=today
        )
    
    def expired(self):
        """Get expired policies"""
        today = timezone.now().date()
        return self.filter(
            end_date__lt=today
        ).exclude(status='cancelled')
    
    def expiring_soon(self, days=30):
        """Get policies expiring within specified days"""
        today = timezone.now().date()
        future_date = today + timedelta(days=days)
        return self.filter(
            status='active',
            end_date__range=[today, future_date]
        )
    
    def by_type(self, policy_type):
        """Get policies by type"""
        return self.filter(policy_type=policy_type)
    
    def by_vehicle(self, vehicle):
        """Get all policies for a vehicle"""
        return self.filter(vehicle=vehicle).order_by('-start_date')


class InsuranceClaimManager(models.Manager):
    """Custom manager for InsuranceClaim model"""
    
    def pending(self):
        """Get pending claims"""
        return self.filter(status='pending')
    
    def approved(self):
        """Get approved claims"""
        return self.filter(status='approved')
    
    def rejected(self):
        """Get rejected claims"""
        return self.filter(status='rejected')
    
    def settled(self):
        """Get settled claims"""
        return self.filter(status='settled')


# ==================== INSURANCE PROVIDER MODEL ====================

class InsuranceProvider(models.Model):
    """
    Model for insurance companies/providers
    """
    
    # Provider Details
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Insurance provider name"
    )
    
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Company registration number"
    )
    
    # Contact Information
    phone_primary = models.CharField(
        max_length=15,
        help_text="Primary contact phone"
    )
    
    phone_secondary = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Secondary contact phone"
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address"
    )
    
    website = models.URLField(
        blank=True,
        null=True,
        help_text="Website URL"
    )
    
    # Address
    physical_address = models.TextField(
        help_text="Physical office address"
    )
    
    postal_address = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Postal address"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="City"
    )
    
    # Contact Person
    contact_person_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Contact person name"
    )
    
    contact_person_phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Contact person phone"
    )
    
    contact_person_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Contact person email"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this provider is active"
    )
    
    # System Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_insurance_providers',
        help_text="User who created this provider"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Insurance Provider'
        verbose_name_plural = 'Insurance Providers'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def active_policies_count(self):
        """Get count of active policies with this provider"""
        return self.policies.filter(status='active').count()
    
    @property
    def total_policies_count(self):
        """Get total count of policies with this provider"""
        return self.policies.count()


# ==================== INSURANCE POLICY MODEL ====================

class InsurancePolicy(models.Model):
    """
    Model for vehicle insurance policies
    """
    
    POLICY_TYPE_CHOICES = [
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('third_party_fire_theft', 'Third Party Fire & Theft'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('renewed', 'Renewed'),
    ]
    
    # Foreign Keys
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.CASCADE,
        related_name='insurance_policies',
        help_text="Vehicle covered by this policy"
    )
    
    provider = models.ForeignKey(
        InsuranceProvider,
        on_delete=models.PROTECT,
        related_name='policies',
        help_text="Insurance provider"
    )
    
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='insurance_policies',
        blank=True,
        null=True,
        help_text="Client/owner of the vehicle (optional)"
    )
    
    # Policy Details
    policy_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="Insurance policy number"
    )
    
    policy_type = models.CharField(
        max_length=50,
        choices=POLICY_TYPE_CHOICES,
        default='comprehensive',
        help_text="Type of insurance coverage"
    )
    
    # Dates
    start_date = models.DateField(
        help_text="Policy start date"
    )
    
    end_date = models.DateField(
        help_text="Policy expiry date"
    )
    
    # Financial Details
    premium_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Insurance premium amount"
    )
    
    sum_insured = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Sum insured/vehicle value"
    )
    
    excess_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Excess/deductible amount"
    )
    
    # Documents
    certificate = models.FileField(
        upload_to='insurance/certificates/%Y/%m/',
        blank=True,
        null=True,
        help_text="Insurance certificate file"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Policy status"
    )
    
    # Renewal Information
    is_renewed = models.BooleanField(
        default=False,
        help_text="Whether this policy has been renewed"
    )
    
    renewed_policy = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_policy',
        help_text="Reference to renewed policy"
    )
    
    # Reminders
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether expiry reminder has been sent"
    )
    
    reminder_sent_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date reminder was sent"
    )
    
    # Additional Information
    coverage_details = models.TextField(
        blank=True,
        null=True,
        help_text="Coverage details and terms"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes"
    )
    
    # System Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_insurance_policies',
        help_text="User who created this policy"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom Manager
    objects = InsurancePolicyManager()
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Insurance Policy'
        verbose_name_plural = 'Insurance Policies'
        indexes = [
            models.Index(fields=['policy_number']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['vehicle']),
        ]
    
    def __str__(self):
        return f"{self.policy_number} - {self.vehicle}"
    
    def save(self, *args, **kwargs):
        """Auto-update status based on dates"""
        today = timezone.now().date()
        
        if self.end_date < today and self.status == 'active':
            self.status = 'expired'
        
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if policy is currently active"""
        today = timezone.now().date()
        return (
            self.status == 'active' and
            self.start_date <= today <= self.end_date
        )
    
    @property
    def is_expired(self):
        """Check if policy has expired"""
        today = timezone.now().date()
        return self.end_date < today
    
    @property
    def days_until_expiry(self):
        """Calculate days until policy expires"""
        today = timezone.now().date()
        if self.end_date >= today:
            delta = self.end_date - today
            return delta.days
        return 0
    
    @property
    def is_expiring_soon(self, days=30):
        """Check if policy is expiring within specified days"""
        return 0 < self.days_until_expiry <= days
    
    @property
    def duration_days(self):
        """Get policy duration in days"""
        delta = self.end_date - self.start_date
        return delta.days
    
    @property
    def duration_months(self):
        """Get policy duration in months (approximate)"""
        return self.duration_days // 30
    
    @property
    def coverage_percentage(self):
        """Calculate coverage percentage (sum insured vs premium)"""
        if self.premium_amount > 0:
            return (self.sum_insured / self.premium_amount) * 100
        return 0
    
    def get_status_color(self):
        """Get color code for policy status"""
        colors = {
            'active': 'green',
            'expired': 'red',
            'cancelled': 'gray',
            'renewed': 'blue',
        }
        return colors.get(self.status, 'gray')


# ==================== INSURANCE CLAIM MODEL ====================

class InsuranceClaim(models.Model):
    """
    Model for insurance claims
    """
    
    CLAIM_TYPE_CHOICES = [
        ('accident', 'Accident'),
        ('theft', 'Theft'),
        ('fire', 'Fire'),
        ('vandalism', 'Vandalism'),
        ('natural_disaster', 'Natural Disaster'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('settled', 'Settled'),
    ]
    
    # Foreign Keys
    policy = models.ForeignKey(
        InsurancePolicy,
        on_delete=models.CASCADE,
        related_name='claims',
        help_text="Insurance policy for this claim"
    )
    
    # Claim Details
    claim_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="Claim reference number"
    )
    
    claim_type = models.CharField(
        max_length=50,
        choices=CLAIM_TYPE_CHOICES,
        help_text="Type of claim"
    )
    
    incident_date = models.DateField(
        help_text="Date of incident"
    )
    
    claim_date = models.DateField(
        default=timezone.now,
        help_text="Date claim was filed"
    )
    
    # Incident Details
    incident_location = models.CharField(
        max_length=500,
        help_text="Location where incident occurred"
    )
    
    incident_description = models.TextField(
        help_text="Detailed description of the incident"
    )
    
    police_report_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Police report/OB number (if applicable)"
    )
    
    # Financial Details
    claimed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount claimed"
    )
    
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount approved by insurer"
    )
    
    settled_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount actually settled/paid"
    )
    
    excess_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Excess amount paid by client"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Claim status"
    )
    
    status_date = models.DateField(
        auto_now=True,
        help_text="Date of last status change"
    )
    
    settlement_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date claim was settled"
    )
    
    # Assessor/Adjuster Details
    assessor_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Insurance assessor name"
    )
    
    assessor_phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Assessor contact phone"
    )
    
    assessment_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of assessment"
    )
    
    assessment_report = models.FileField(
        upload_to='insurance/assessments/%Y/%m/',
        blank=True,
        null=True,
        help_text="Assessment report file"
    )
    
    # Documents
    supporting_documents = models.FileField(
        upload_to='insurance/claims/%Y/%m/',
        blank=True,
        null=True,
        help_text="Supporting documents (photos, receipts, etc.)"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes and updates"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for rejection (if applicable)"
    )
    
    # System Fields
    filed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='filed_insurance_claims',
        help_text="User who filed this claim"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom Manager
    objects = InsuranceClaimManager()
    
    class Meta:
        ordering = ['-claim_date']
        verbose_name = 'Insurance Claim'
        verbose_name_plural = 'Insurance Claims'
        indexes = [
            models.Index(fields=['claim_number']),
            models.Index(fields=['status']),
            models.Index(fields=['claim_date']),
            models.Index(fields=['incident_date']),
        ]
    
    def __str__(self):
        return f"Claim {self.claim_number} - {self.policy.vehicle}"
    
    def save(self, *args, **kwargs):
        """Generate claim number if not provided"""
        if not self.claim_number:
            # Generate claim number: CLM-YYYYMMDD-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            last_claim = InsuranceClaim.objects.filter(
                claim_number__startswith=f'CLM-{date_str}'
            ).order_by('-claim_number').first()
            
            if last_claim:
                last_num = int(last_claim.claim_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.claim_number = f'CLM-{date_str}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    @property
    def vehicle(self):
        """Get vehicle from policy"""
        return self.policy.vehicle
    
    @property
    def client(self):
        """Get client from policy"""
        return self.policy.client
    
    @property
    def provider(self):
        """Get provider from policy"""
        return self.policy.provider
    
    @property
    def days_since_filed(self):
        """Calculate days since claim was filed"""
        today = timezone.now().date()
        delta = today - self.claim_date
        return delta.days
    
    @property
    def is_pending(self):
        """Check if claim is pending"""
        return self.status in ['pending', 'under_review']
    
    @property
    def approval_percentage(self):
        """Calculate percentage of claim approved"""
        if self.claimed_amount > 0:
            return (self.approved_amount / self.claimed_amount) * 100
        return 0
    
    def get_status_color(self):
        """Get color code for claim status"""
        colors = {
            'pending': 'yellow',
            'under_review': 'blue',
            'approved': 'green',
            'rejected': 'red',
            'settled': 'teal',
        }
        return colors.get(self.status, 'gray')


# ==================== INSURANCE PAYMENT MODEL ====================

class InsurancePayment(models.Model):
    """
    Model for insurance premium payments
    """
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('direct_debit', 'Direct Debit'),
    ]
    
    # Foreign Keys
    policy = models.ForeignKey(
        InsurancePolicy,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Insurance policy this payment is for"
    )
    
    # Payment Details
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payment amount"
    )
    
    payment_date = models.DateField(
        default=timezone.now,
        help_text="Date payment was made"
    )
    
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        help_text="Method of payment"
    )
    
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Transaction reference number"
    )
    
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Payment receipt number"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes"
    )
    
    # System Fields
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_insurance_payments',
        help_text="User who recorded this payment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Insurance Payment'
        verbose_name_plural = 'Insurance Payments'
        indexes = [
            models.Index(fields=['payment_date']),
            models.Index(fields=['policy']),
        ]
    
    def __str__(self):
        return f"Payment {self.receipt_number} - KES {self.amount:,.2f}"
    
    def save(self, *args, **kwargs):
        """Generate receipt number if not provided"""
        if not self.receipt_number:
            # Generate receipt number: INS-YYYYMMDD-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            last_payment = InsurancePayment.objects.filter(
                receipt_number__startswith=f'INS-{date_str}'
            ).order_by('-receipt_number').first()
            
            if last_payment:
                last_num = int(last_payment.receipt_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.receipt_number = f'INS-{date_str}-{new_num:04d}'
        
        super().save(*args, **kwargs)