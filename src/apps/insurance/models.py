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


# ==================== INSURANCE AGENT MODEL ====================

class InsuranceAgent(models.Model):
    """
    An individual agent who sells insurance policies on behalf of a provider.
    Used to track how many policies we've taken through each agent and what we owe them.
    """
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True, null=True)
    id_number = models.CharField(
        'ID / License Number', max_length=100, blank=True,
        help_text='Agent ID or license number'
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Insurance Agent'
        verbose_name_plural = 'Insurance Agents'

    def __str__(self):
        return self.name

    @property
    def total_policies(self):
        return self.policies.count()

    @property
    def total_buying_price(self):
        from django.db.models import Sum
        return self.policies.aggregate(total=Sum('buying_price'))['total'] or Decimal('0.00')

    @property
    def total_selling_price(self):
        from django.db.models import Sum
        return self.policies.aggregate(total=Sum('selling_price'))['total'] or Decimal('0.00')

    @property
    def total_owed(self):
        """Remaining balance: total buying price minus all payments made."""
        return max(Decimal('0.00'), self.total_buying_price - self.total_payments_made)

    @property
    def total_payments_made(self):
        from django.db.models import Sum
        return self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')


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

    VEHICLE_USAGE_CHOICES = [
        ('private', 'Private'),
        ('psv', 'PSV'),
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

    vehicle_usage = models.CharField(
        max_length=20,
        choices=VEHICLE_USAGE_CHOICES,
        default='private',
        help_text='Vehicle usage category for the policy'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Policy status"
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
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
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

    # Dealer pricing
    buying_price = models.DecimalField(
        'Buying Price (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount dealer paid the insurance company'
    )

    selling_price = models.DecimalField(
        'Selling Price (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount charged to client for insurance'
    )

    # Agent details
    agent_name = models.CharField(
        'Agent Name',
        max_length=200,
        blank=True,
        help_text='Insurance agent name'
    )

    agent_id = models.CharField(
        'Agent ID / Number',
        max_length=100,
        blank=True,
        help_text='Agent ID, license number, or phone'
    )

    insurance_agent = models.ForeignKey(
        'InsuranceAgent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies',
        help_text='Linked insurance agent (ledger)',
    )

    # Dealer payment to agent
    DEALER_PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    dealer_payment_status = models.CharField(
        'Dealer Payment Status',
        max_length=10,
        choices=DEALER_PAYMENT_STATUS_CHOICES,
        default='unpaid',
        help_text='Whether we have paid the agent for this policy',
    )

    # Payment type for insurance
    INSURANCE_PAYMENT_TYPE_CHOICES = [
        ('full', 'Full Payment'),
        ('flexible', 'Flexible Installments'),
        ('deduct_from_deposit', 'Deduct from Deposit'),
    ]

    payment_type = models.CharField(
        'Payment Type',
        max_length=30,
        choices=INSURANCE_PAYMENT_TYPE_CHOICES,
        default='full',
        help_text='How the client pays for insurance',
    )

    INSURANCE_PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('other', 'Other'),
    ]

    insurance_payment_method = models.CharField(
        'Payment Method',
        max_length=30,
        choices=INSURANCE_PAYMENT_METHOD_CHOICES,
        default='cash',
        help_text='Method used to pay for insurance',
    )

    # Individual payment plan for insurance
    has_payment_plan = models.BooleanField(
        'Has Payment Plan',
        default=False,
        help_text='Whether client pays insurance in installments'
    )

    insurance_deposit = models.DecimalField(
        'Insurance Deposit (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
    )

    insurance_installment_months = models.PositiveIntegerField(
        'Insurance Installment Months',
        null=True,
        blank=True,
    )

    insurance_monthly_installment = models.DecimalField(
        'Monthly Installment (KES)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    insurance_total_paid = models.DecimalField(
        'Total Paid (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    insurance_balance = models.DecimalField(
        'Insurance Balance (KES)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    # Interest & Fees
    insurance_interest_rate = models.DecimalField(
        'Insurance Interest Rate (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Annual interest rate for payment plan (%)'
    )

    insurance_total_with_interest = models.DecimalField(
        'Total with Interest (KES)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Auto-calculated total including interest'
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
        """
        Auto-update status based on dates
        Auto-calculate monthly installment, total with interest, and balance
        """
        today = timezone.now().date()
        
        if self.end_date < today and self.status == 'active':
            self.status = 'expired'
        
        # Auto-calculate payment plan fields if has_payment_plan is True
        if self.has_payment_plan and self.insurance_deposit is not None and \
           self.insurance_installment_months and self.selling_price:
            
            # Balance = remaining unpaid (selling price minus all payments made so far)
            balance_after_deposit = self.selling_price - self.insurance_deposit
            self.insurance_balance = max(Decimal('0.00'), self.selling_price - self.insurance_total_paid)

            # Calculate total with interest
            if self.insurance_interest_rate > Decimal('0.00'):
                rate = Decimal(str(self.insurance_interest_rate)) / Decimal('100.00')
                months = Decimal(str(self.insurance_installment_months))
                interest = balance_after_deposit * rate * (months / Decimal('12.00'))
                self.insurance_total_with_interest = balance_after_deposit + interest
            else:
                self.insurance_total_with_interest = balance_after_deposit
            
            # Calculate monthly installment
            if self.insurance_installment_months and self.insurance_total_with_interest:
                self.insurance_monthly_installment = round(
                    self.insurance_total_with_interest / Decimal(str(self.insurance_installment_months)),
                    2
                )
        
        super().save(*args, **kwargs)
        
        # Generate payment schedule if this is a new policy with payment plan
        if self.has_payment_plan and self.insurance_installment_months:
            # Check if schedules already exist
            if not self.insurance_payment_schedules.exists():
                self.generate_insurance_payment_schedule()
    
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
    
    @property
    def is_schedule_generated(self):
        """Check if payment schedule has been generated"""
        return self.insurance_payment_schedules.exists()
    
    @property
    def total_interest(self):
        """Calculate total interest amount"""
        if self.has_payment_plan and self.insurance_total_with_interest and self.insurance_balance:
            return self.insurance_total_with_interest - self.insurance_balance
        return Decimal('0.00')
    
    @property
    def accumulated_late_fees(self):
        """Calculate accumulated late fees from overdue schedules"""
        total_fees = Decimal('0.00')
        for schedule in self.insurance_payment_schedules.filter(is_paid=False):
            total_fees += schedule.late_fee_applied
        return total_fees
    
    def get_total_cost_with_fees(self):
        """Get total cost including deposit, interest, and late fees"""
        if not self.has_payment_plan:
            return self.selling_price
        
        total = Decimal('0.00')
        total += self.insurance_deposit  # Deposit
        total += self.total_interest      # Interest
        total += self.accumulated_late_fees  # Late fees
        return total
    
    def generate_insurance_payment_schedule(self):
        """
        Generate payment schedules for insurance payment plan
        Creates monthly payment schedule entries
        """
        from dateutil.relativedelta import relativedelta
        
        # Delete existing schedules
        self.insurance_payment_schedules.all().delete()
        
        # Determine starting date for first payment (month after policy start)
        current_date = self.start_date + relativedelta(months=1)
        
        for i in range(1, self.insurance_installment_months + 1):
            # Create due date on same day of month as start_date
            try:
                due_date = current_date.replace(day=self.start_date.day)
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 31)
                # Use last day of month
                due_date = (current_date + relativedelta(day=31))
            
            InsurancePaymentSchedule.objects.create(
                policy=self,
                installment_number=i,
                due_date=due_date,
                amount_due=self.insurance_monthly_installment
            )
            
            # Move to next month
            current_date = due_date + relativedelta(months=1)


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
    def agent(self):
        """Get insurance agent from policy"""
        return self.policy.insurance_agent

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


# ==================== INSURANCE PAYMENT SCHEDULE MODEL ====================

class InsurancePaymentScheduleManager(models.Manager):
    """Custom manager for InsurancePaymentSchedule model"""
    
    def pending(self):
        """Get pending payment schedules"""
        return self.filter(is_paid=False)
    
    def paid(self):
        """Get paid schedules"""
        return self.filter(is_paid=True)
    
    def overdue(self):
        """Get overdue payment schedules"""
        today = timezone.now().date()
        return self.filter(
            is_paid=False,
            due_date__lt=today
        )
    
    def due_this_month(self):
        """Get schedules due this month"""
        now = timezone.now()
        return self.filter(
            is_paid=False,
            due_date__year=now.year,
            due_date__month=now.month
        )


class InsurancePaymentSchedule(models.Model):
    """
    Model for individual insurance payment schedule entries
    Tracks when each insurance installment is due
    """
    
    # Foreign Keys
    policy = models.ForeignKey(
        InsurancePolicy,
        on_delete=models.CASCADE,
        related_name='insurance_payment_schedules',
        help_text="Insurance policy this schedule belongs to"
    )
    
    payment = models.ForeignKey(
        InsurancePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
        help_text="Insurance payment that fulfilled this schedule"
    )
    
    # Schedule Details
    installment_number = models.PositiveIntegerField(
        help_text="Installment number (1, 2, 3, etc.)"
    )
    
    due_date = models.DateField(
        help_text="Date this installment is due"
    )
    
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount due for this installment"
    )
    
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount paid for this installment"
    )
    
    late_fee_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Late fees applied (0.1% per day, max 50% of amount due)"
    )
    
    # Status
    is_paid = models.BooleanField(
        default=False,
        help_text="Whether this installment has been paid"
    )
    
    payment_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date payment was received"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes"
    )
    
    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom Manager
    objects = InsurancePaymentScheduleManager()
    
    class Meta:
        ordering = ['installment_number']
        verbose_name = 'Insurance Payment Schedule'
        verbose_name_plural = 'Insurance Payment Schedules'
        unique_together = ['policy', 'installment_number']
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['is_paid']),
            models.Index(fields=['policy', 'due_date']),
        ]
    
    def __str__(self):
        return f"Installment {self.installment_number} - Due: {self.due_date}"
    
    @property
    def is_overdue(self):
        """Check if this schedule is overdue"""
        if not self.is_paid:
            return timezone.now().date() > self.due_date
        return False
    
    @property
    def days_overdue(self):
        """Calculate number of days overdue"""
        if self.is_overdue:
            delta = timezone.now().date() - self.due_date
            return delta.days
        return 0
    
    @property
    def remaining_amount(self):
        """Calculate remaining amount to be paid"""
        return self.amount_due - self.amount_paid
    
    @property
    def is_partial_payment(self):
        """Check if partial payment has been made"""
        return self.amount_paid > 0 and self.amount_paid < self.amount_due
    
    def calculate_late_fee(self):
        """
        Calculate late fee for overdue installment
        0.1% per day, capped at 50% of amount due
        """
        if self.is_overdue and not self.is_paid:
            days_overdue = self.days_overdue
            daily_rate = Decimal('0.001')  # 0.1% per day
            fee = self.amount_due * daily_rate * Decimal(str(days_overdue))
            
            # Cap at 50% of amount due
            max_fee = self.amount_due * Decimal('0.50')
            return min(fee, max_fee)
        return Decimal('0.00')
    
    def update_late_fees(self):
        """Update late fees and save"""
        self.late_fee_applied = self.calculate_late_fee()
        self.save(update_fields=['late_fee_applied'])
    
    def mark_as_paid(self, payment, amount=None):
        """Mark this schedule as paid"""
        if payment.payment_date and payment.payment_date > timezone.now().date():
            # A future-dated payment is scheduled, not yet received.
            return

        if amount is None:
            amount = self.remaining_amount
        
        self.payment = payment
        self.amount_paid += amount
        self.payment_date = payment.payment_date
        
        if self.amount_paid >= self.amount_due:
            self.is_paid = True

        self.save()


# ==================== INSURANCE AGENT PAYMENT MODEL ====================

class InsuranceAgentPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mpesa', 'M-Pesa'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    agent = models.ForeignKey(
        InsuranceAgent, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(
        'Amount (KES)', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateField('Payment Date', default=timezone.now)
    payment_method = models.CharField(
        'Payment Method', max_length=20,
        choices=PAYMENT_METHOD_CHOICES, default='bank_transfer'
    )
    reference_number = models.CharField('Reference / Receipt No.', max_length=100, blank=True)
    notes = models.TextField('Notes', blank=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='insurance_agent_payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Insurance Agent Payment'
        verbose_name_plural = 'Insurance Agent Payments'
        db_table = 'insurance_agent_payments'

    def __str__(self):
        return f"Payment KES {self.amount:,.0f} to {self.agent.name} on {self.payment_date}"