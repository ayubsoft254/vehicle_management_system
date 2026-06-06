"""
Models for the payments app
Handles payment records, installment plans, and payment schedules
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from dateutil.relativedelta import relativedelta

User = get_user_model()


# ==================== CUSTOM MANAGERS ====================

class PaymentManager(models.Manager):
    """Custom manager for Payment model"""
    
    def this_month(self):
        """Get payments for current month"""
        now = timezone.now()
        return self.filter(
            payment_date__year=now.year,
            payment_date__month=now.month
        )
    
    def this_year(self):
        """Get payments for current year"""
        now = timezone.now()
        return self.filter(payment_date__year=now.year)
    
    def by_method(self, method):
        """Get payments by payment method"""
        return self.filter(payment_method=method)
    
    def total_collected(self):
        """Get total amount collected"""
        return self.aggregate(models.Sum('amount'))['amount__sum'] or 0
    
    def by_client(self, client):
        """Get all payments for a specific client"""
        return self.filter(client_vehicle__client=client)


class InstallmentPlanManager(models.Manager):
    """Custom manager for InstallmentPlan model"""
    
    def active(self):
        """Get active installment plans"""
        return self.filter(is_active=True, is_completed=False)
    
    def completed(self):
        """Get completed installment plans"""
        return self.filter(is_completed=True)
    
    def overdue(self):
        """Get overdue installment plans"""
        today = timezone.now().date()
        return self.filter(
            is_active=True,
            is_completed=False,
            end_date__lt=today
        )


class PaymentScheduleManager(models.Manager):
    """Custom manager for PaymentSchedule model"""
    
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


# ==================== PAYMENT MODEL ====================

class Payment(models.Model):
    """
    Model for recording individual payments
    Links to ClientVehicle from clients app
    """
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('kcb_ke', 'KCB KE'),
        ('absa_ke', 'ABSA KE'),
        ('equity_ke', 'EQUITY KE'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('mixed', 'Multiple Methods'),
        ('other', 'Other'),
    ]
    
    # Foreign Keys
    client_vehicle = models.ForeignKey(
        'clients.ClientVehicle',
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Vehicle purchase this payment is for"
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
        help_text="Date payment was received"
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
        help_text="Transaction reference number (M-Pesa code, cheque number, etc.)"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the payment"
    )
    
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Receipt number for this payment"
    )
    
    # System Fields
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_payments',
        help_text="User who recorded this payment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom Manager
    objects = PaymentManager()
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['client_vehicle', 'payment_date']),
        ]
    
    def __str__(self):
        # Convert amount to float to ensure proper formatting (avoids SafeString formatting issues)
        amount_value = float(self.amount) if self.amount else 0.0
        return f"Payment {self.receipt_number or self.pk} - KES {amount_value:,.2f}"
    
    def save(self, *args, **kwargs):
        """Generate receipt number if not provided"""
        if not self.receipt_number:
            # Generate receipt number: RCP-YYYYMMDD-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            last_receipt = Payment.objects.filter(
                receipt_number__startswith=f'RCP-{date_str}'
            ).order_by('-receipt_number').first()
            
            if last_receipt:
                last_num = int(last_receipt.receipt_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.receipt_number = f'RCP-{date_str}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    @property
    def client(self):
        """Get the client for this payment"""
        return self.client_vehicle.client
    
    @property
    def vehicle(self):
        """Get the vehicle for this payment"""
        return self.client_vehicle.vehicle

    @property
    def is_split(self):
        """Check if this payment uses multiple methods"""
        return self.splits.exists()


# ==================== PAYMENT SPLIT MODEL ====================

class PaymentSplit(models.Model):
    """
    Allows a single Payment to be split across multiple payment methods.
    e.g. KES 200,000 = 15,000 Bank + 20,000 MPesa + 165,000 Cash
    """

    PAYMENT_METHOD_CHOICES = Payment.PAYMENT_METHOD_CHOICES

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='splits',
        help_text='The parent payment this split belongs to'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        help_text='Payment method for this portion'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Amount paid via this method'
    )

    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Transaction reference / M-Pesa code / Cheque number'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_splits'
        verbose_name = 'Payment Split'
        verbose_name_plural = 'Payment Splits'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_payment_method_display()} — KES {self.amount:,.2f}"


# ==================== INSTALLMENT PLAN MODEL ====================

class InstallmentPlan(models.Model):
    """
    Model for installment payment plans
    Defines the payment schedule for a vehicle purchase
    """
    
    # Foreign Keys
    client_vehicle = models.OneToOneField(
        'clients.ClientVehicle',
        on_delete=models.CASCADE,
        related_name='installment_plan',
        help_text="Vehicle purchase this plan is for"
    )
    
    # Plan Details
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total purchase amount"
    )
    
    deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text="Initial deposit paid"
    )
    
    monthly_installment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        blank=True,
        null=True,
        help_text="Monthly installment amount (auto-calculated if blank)"
    )
    
    number_of_installments = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of monthly installments"
    )
    
    # Dates
    start_date = models.DateField(
        help_text="Date when payment plan starts"
    )
    
    end_date = models.DateField(
        blank=True,
        null=True,
        help_text="Expected completion date"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is active"
    )
    
    is_completed = models.BooleanField(
        default=False,
        help_text="Whether all payments have been made"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the plan"
    )
    
    # System Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_installment_plans',
        help_text="User who created this plan"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom Manager
    objects = InstallmentPlanManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Installment Plan'
        verbose_name_plural = 'Installment Plans'
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_active', 'is_completed']),
        ]
    
    def __str__(self):
        return f"Plan for {self.client_vehicle.client.get_full_name()} - {self.client_vehicle.vehicle}"
    
    def save(self, *args, **kwargs):
        """Calculate end date and monthly installment if not provided"""
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + relativedelta(months=self.number_of_installments)
            
        if not self.monthly_installment and self.total_amount is not None and self.deposit is not None and self.number_of_installments:
            principal = self.total_amount - self.deposit
            # No interest - balance is simply selling price - deposit
            self.monthly_installment = round(principal / Decimal(str(self.number_of_installments)), 2)
            
        super().save(*args, **kwargs)
    
    @property
    def balance_after_deposit(self):
        """Calculate balance after deposit"""
        return self.total_amount - self.deposit
    
    @property
    def deposit_amount(self):
        """Alias for deposit"""
        return self.deposit
    
    @property
    def remainder_amount(self):
        """Alias for balance after deposit"""
        return self.balance_after_deposit
    
    @property
    def monthly_amount(self):
        """Alias for monthly_installment"""
        return self.monthly_installment
    
    @property
    def installment_months(self):
        """Alias for number_of_installments"""
        return self.number_of_installments
    
    @property
    def total_with_interest(self):
        """Calculate total amount including interest"""
        if self.interest_rate > 0:
            principal = self.balance_after_deposit
            rate = self.interest_rate / 100
            months = self.number_of_installments
            # Simple interest calculation
            interest = principal * rate * (months / 12)
            return principal + interest
        return self.balance_after_deposit
    
    @property
    def total_interest(self):
        """Calculate total interest amount"""
        return self.total_with_interest - self.balance_after_deposit
    
    @property
    def monthly_installment_with_interest(self):
        """Calculate monthly installment including interest"""
        return self.total_with_interest / self.number_of_installments
    
    @property
    def amount_paid(self):
        """Get total amount paid so far"""
        return self.client_vehicle.total_paid
        
    @property
    def total_paid(self):
        """Alias for amount_paid used in some templates"""
        return self.amount_paid
    
    @property
    def remaining_balance(self):
        """Get remaining balance"""
        return self.client_vehicle.balance
    
    @property
    def payment_progress(self):
        """Calculate payment progress percentage"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0
    
    @property
    def accumulated_late_fees(self):
        """Calculate accumulated late fees from overdue schedules"""
        total_fees = Decimal('0.00')
        for schedule in self.payment_schedules.filter(is_paid=False):
            schedule.update_late_fees()  # Update before summing
            total_fees += schedule.late_fee_applied
        return total_fees
    
    def get_total_cost_with_fees(self):
        """Get total cost including deposit, interest, and late fees"""
        total = self.total_amount  # Base amount
        total += self.total_interest  # Add interest
        total += self.accumulated_late_fees  # Add accumulated late fees
        return total
    
    @property
    def is_overdue(self):
        """Check if plan is overdue"""
        if not self.is_completed and self.end_date:
            return timezone.now().date() > self.end_date
        return False
    
    def generate_payment_schedule(self):
        """
        Generate payment schedules for this plan
        Supports monthly (on specific day) and weekly (on specific weekday) payment patterns
        """
        from dateutil.relativedelta import relativedelta
        
        # Delete existing schedules
        self.payment_schedules.all().delete()
        
        # Get payment configuration from client vehicle
        client_vehicle = self.client_vehicle
        remainder_type = getattr(client_vehicle, 'remainder_payment_type', 'monthly')
        monthly_date = getattr(client_vehicle, 'monthly_payment_date', None)
        weekly_day = getattr(client_vehicle, 'weekly_payment_day', None)
        
        current_date = self.start_date
        
        if remainder_type == 'weekly' and weekly_day is not None:
            # Weekly payment schedule - every specific weekday (0=Monday, 6=Sunday)
            # Move to first occurrence of the target weekday
            days_until_target = (weekly_day - current_date.weekday()) % 7
            if days_until_target == 0 and current_date != self.start_date:
                # Already on target day, move to next occurrence
                days_until_target = 7
            current_date = current_date + timedelta(days=days_until_target)
            
            for i in range(1, self.number_of_installments + 1):
                PaymentSchedule.objects.create(
                    installment_plan=self,
                    installment_number=i,
                    due_date=current_date,
                    amount_due=self.monthly_installment
                )
                current_date = current_date + timedelta(weeks=1)
        
        else:
            # Monthly payment schedule - on specific day of month
            if monthly_date is None:
                monthly_date = self.start_date.day
            
            for i in range(1, self.number_of_installments + 1):
                # Try to set to the specified day of month
                try:
                    target_date = current_date.replace(day=monthly_date)
                except ValueError:
                    # Day doesn't exist in this month (e.g., Feb 31)
                    # Use last day of month
                    target_date = current_date + relativedelta(day=31)
                
                # If target date is before or equal to current date, move to next month
                if target_date <= self.start_date and i == 1:
                    # For first payment, if target is in past, move to next month
                    target_date = (current_date + relativedelta(months=1)).replace(day=monthly_date)
                
                PaymentSchedule.objects.create(
                    installment_plan=self,
                    installment_number=i,
                    due_date=target_date,
                    amount_due=self.monthly_installment
                )
                
                # Move to next month
                current_date = target_date + relativedelta(months=1)


# ==================== PAYMENT SCHEDULE MODEL ====================

class PaymentSchedule(models.Model):
    """
    Model for individual payment schedule entries
    Tracks when each installment is due
    """
    
    # Foreign Keys
    installment_plan = models.ForeignKey(
        InstallmentPlan,
        on_delete=models.CASCADE,
        related_name='payment_schedules',
        help_text="Installment plan this schedule belongs to"
    )
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
        help_text="Payment that fulfilled this schedule"
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
    objects = PaymentScheduleManager()
    
    class Meta:
        ordering = ['installment_number']
        verbose_name = 'Payment Schedule'
        verbose_name_plural = 'Payment Schedules'
        unique_together = ['installment_plan', 'installment_number']
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['is_paid']),
            models.Index(fields=['installment_plan', 'due_date']),
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


# ==================== PAYMENT REMINDER MODEL ====================

class PaymentReminder(models.Model):
    """
    Model for tracking payment reminders sent to clients
    """
    
    REMINDER_TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('call', 'Phone Call'),
        ('letter', 'Physical Letter'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('responded', 'Client Responded'),
    ]
    
    # Foreign Keys
    payment_schedule = models.ForeignKey(
        PaymentSchedule,
        on_delete=models.CASCADE,
        related_name='reminders',
        help_text="Payment schedule this reminder is for"
    )
    
    # Reminder Details
    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPE_CHOICES,
        default='sms',
        help_text="Type of reminder"
    )
    
    reminder_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date reminder was sent"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Status of the reminder"
    )
    
    message = models.TextField(
        help_text="Reminder message content"
    )
    
    # Response
    client_response = models.TextField(
        blank=True,
        null=True,
        help_text="Client's response to the reminder"
    )
    
    response_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date client responded"
    )
    
    # System Fields
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_reminders',
        help_text="User who sent this reminder"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-reminder_date']
        verbose_name = 'Payment Reminder'
        verbose_name_plural = 'Payment Reminders'
        indexes = [
            models.Index(fields=['reminder_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.get_reminder_type_display()} - {self.payment_schedule}"


# ==================== DARAJA PAYBILL TRACKING MODELS ====================

class MpesaSTKRequest(models.Model):
    """Stores M-Pesa STK push requests and asynchronous callback outcomes."""

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_TIMEOUT = 'timeout'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    client_vehicle = models.ForeignKey(
        'clients.ClientVehicle',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='mpesa_stk_requests'
    )
    payment = models.OneToOneField(
        'Payment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='mpesa_stk_request'
    )

    account_reference = models.CharField(max_length=120, blank=True, default='')
    payment_type = models.CharField(max_length=40, blank=True, default='')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    merchant_request_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    checkout_request_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    response_code = models.CharField(max_length=20, blank=True, default='')
    response_description = models.TextField(blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_code = models.IntegerField(blank=True, null=True)
    result_desc = models.TextField(blank=True, default='')

    mpesa_receipt_number = models.CharField(max_length=40, blank=True, default='', db_index=True)
    transaction_date = models.DateTimeField(blank=True, null=True)

    raw_request_payload = models.JSONField(default=dict, blank=True)
    raw_response_payload = models.JSONField(default=dict, blank=True)
    raw_callback_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'M-Pesa STK Request'
        verbose_name_plural = 'M-Pesa STK Requests'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['account_reference']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        account = self.account_reference or 'no-ref'
        return f"{account} - KES {self.amount:,.2f} ({self.get_status_display()})"

class PaybillTransaction(models.Model):
    """Stores incoming M-Pesa C2B confirmation transactions for the paybill."""

    trans_id = models.CharField(max_length=40, unique=True, db_index=True)
    trans_time = models.DateTimeField(blank=True, null=True)
    trans_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    business_short_code = models.CharField(max_length=20, blank=True, default='')
    bill_ref_number = models.CharField(max_length=120, blank=True, default='')
    invoice_number = models.CharField(max_length=120, blank=True, default='')

    org_account_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        help_text='Organization account balance as shared in C2B callback, if available.'
    )

    msisdn = models.CharField(max_length=20, blank=True, default='')
    first_name = models.CharField(max_length=80, blank=True, default='')
    middle_name = models.CharField(max_length=80, blank=True, default='')
    last_name = models.CharField(max_length=80, blank=True, default='')

    raw_payload = models.JSONField(default=dict, blank=True)
    is_linked_to_payment = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-trans_time', '-created_at']
        verbose_name = 'Paybill Transaction'
        verbose_name_plural = 'Paybill Transactions'
        indexes = [
            models.Index(fields=['msisdn']),
            models.Index(fields=['bill_ref_number']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.trans_id} - KES {self.trans_amount:,.2f}"

    @property
    def payer_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(part for part in parts if part).strip() or 'Unknown'


class PaybillBalanceSnapshot(models.Model):
    """Stores results from Daraja account balance API callbacks."""

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_TIMEOUT = 'timeout'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)

    request_reference = models.CharField(max_length=120, blank=True, default='', db_index=True)
    conversation_id = models.CharField(max_length=120, blank=True, default='')
    originator_conversation_id = models.CharField(max_length=120, blank=True, default='')
    result_code = models.IntegerField(blank=True, null=True)
    result_desc = models.TextField(blank=True, default='')

    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Paybill Balance Snapshot'
        verbose_name_plural = 'Paybill Balance Snapshots'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Paybill balance ({self.get_status_display()}) @ {self.created_at:%Y-%m-%d %H:%M}"