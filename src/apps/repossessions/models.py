"""
Models for the repossessions app.
Handles vehicle repossession process management and tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

User = get_user_model()


class Repossession(models.Model):
    """Main repossession record for defaulted payments."""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('NOTICE_SENT', 'Notice Sent'),
        ('IN_PROGRESS', 'In Progress'),
        ('VEHICLE_RECOVERED', 'Vehicle Recovered'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    REASON_CHOICES = [
        ('PAYMENT_DEFAULT', 'Payment Default'),
        ('BREACH_OF_CONTRACT', 'Breach of Contract'),
        ('INSURANCE_LAPSE', 'Insurance Lapse'),
        ('UNAUTHORIZED_USE', 'Unauthorized Use'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    repossession_number = models.CharField(max_length=50, unique=True, editable=False)
    
    # Related Records
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.PROTECT,
        related_name='repossessions'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='repossessions'
    )
    
    # Repossession Details
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Financial Details
    outstanding_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total amount owed"
    )
    payments_missed = models.PositiveIntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Important Dates
    initiated_date = models.DateField(default=timezone.now)
    notice_sent_date = models.DateField(null=True, blank=True)
    recovery_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_repossessions',
        help_text="Agent/officer assigned to this repossession"
    )
    
    # Vehicle Location
    last_known_location = models.TextField(blank=True)
    current_location = models.TextField(
        blank=True,
        help_text="Current location of vehicle (if recovered)"
    )
    
    # Recovery Details
    recovery_method = models.CharField(
        max_length=100,
        blank=True,
        help_text="How the vehicle was recovered"
    )
    recovery_agent = models.CharField(max_length=200, blank=True)
    
    # Legal Information
    legal_notice_sent = models.BooleanField(default=False)
    legal_notice_date = models.DateField(null=True, blank=True)
    court_order_obtained = models.BooleanField(default=False)
    court_order_date = models.DateField(null=True, blank=True)
    court_order_number = models.CharField(max_length=100, blank=True)
    
    # Costs
    recovery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    storage_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    legal_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    other_costs = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )
    
    # Resolution
    resolution_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('PAID_IN_FULL', 'Paid in Full'),
            ('AUCTIONED', 'Vehicle Auctioned'),
            ('RETURNED', 'Returned to Client'),
            ('WRITTEN_OFF', 'Written Off'),
            ('OTHER', 'Other'),
        ]
    )
    resolution_notes = models.TextField(blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_repossessions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Repossession"
        verbose_name_plural = "Repossessions"
        ordering = ['-initiated_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'initiated_date']),
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['client', 'status']),
        ]
    
    def __str__(self):
        return f"{self.repossession_number} - {self.vehicle}"
    
    def save(self, *args, **kwargs):
        """Generate repossession number and calculate total cost."""
        if not self.repossession_number:
            # Generate number: REPO-YYYY-XXX
            from datetime import datetime
            year = datetime.now().year
            prefix = f"REPO-{year}"
            
            last_repo = Repossession.objects.filter(
                repossession_number__startswith=prefix
            ).order_by('-repossession_number').first()
            
            if last_repo:
                last_num = int(last_repo.repossession_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.repossession_number = f"{prefix}-{new_num:04d}"
        
        # Calculate total cost
        self.total_cost = (
            self.recovery_cost +
            self.storage_cost +
            self.legal_cost +
            self.other_costs
        )
        
        super().save(*args, **kwargs)
    
    def get_days_in_process(self):
        """Calculate days since initiation."""
        if self.completion_date:
            end_date = self.completion_date
        else:
            end_date = date.today()
        
        return (end_date - self.initiated_date).days
    
    def get_total_amount_due(self):
        """Calculate total amount including costs."""
        return self.outstanding_amount + self.total_cost
    
    def can_cancel(self):
        """Check if repossession can be cancelled."""
        return self.status not in ['COMPLETED', 'CANCELLED']
    
    def mark_as_recovered(self, recovery_date=None, location=None):
        """Mark vehicle as recovered."""
        self.status = 'VEHICLE_RECOVERED'
        self.recovery_date = recovery_date or date.today()
        if location:
            self.current_location = location
        self.save()
    
    def mark_as_completed(self, resolution_type, notes=''):
        """Mark repossession as completed."""
        self.status = 'COMPLETED'
        self.completion_date = date.today()
        self.resolution_type = resolution_type
        self.resolution_notes = notes
        self.save()


class RepossessionDocument(models.Model):
    """Documents related to repossession process."""
    
    DOCUMENT_TYPE_CHOICES = [
        ('NOTICE', 'Repossession Notice'),
        ('COURT_ORDER', 'Court Order'),
        ('POLICE_REPORT', 'Police Report'),
        ('RECOVERY_REPORT', 'Recovery Report'),
        ('LEGAL_LETTER', 'Legal Letter'),
        ('PHOTO', 'Photo Evidence'),
        ('OTHER', 'Other'),
    ]
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    file = models.FileField(upload_to='repossessions/documents/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    file_type = models.CharField(max_length=50)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Repossession Document"
        verbose_name_plural = "Repossession Documents"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.repossession.repossession_number}"
    
    def get_file_size_display(self):
        """Return human-readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


class RepossessionNote(models.Model):
    """Activity notes and updates for repossession."""
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    
    note = models.TextField()
    
    # Optional categorization
    note_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('UPDATE', 'Status Update'),
            ('CONTACT', 'Client Contact'),
            ('LOCATION', 'Location Info'),
            ('LEGAL', 'Legal Action'),
            ('RECOVERY', 'Recovery Attempt'),
            ('OTHER', 'Other'),
        ]
    )
    
    is_important = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Repossession Note"
        verbose_name_plural = "Repossession Notes"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note for {self.repossession.repossession_number} - {self.created_at.strftime('%Y-%m-%d')}"


class RepossessionExpense(models.Model):
    """Track expenses related to repossession."""
    
    EXPENSE_TYPE_CHOICES = [
        ('RECOVERY', 'Recovery Fee'),
        ('TOWING', 'Towing Fee'),
        ('STORAGE', 'Storage Fee'),
        ('LEGAL', 'Legal Fee'),
        ('COURT', 'Court Fee'),
        ('TRANSPORT', 'Transport'),
        ('DOCUMENTATION', 'Documentation'),
        ('OTHER', 'Other'),
    ]
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    expense_date = models.DateField(default=timezone.now)
    vendor = models.CharField(max_length=200, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Repossession Expense"
        verbose_name_plural = "Repossession Expenses"
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.get_expense_type_display()} - {self.amount}"


class RepossessionStatusHistory(models.Model):
    """Track status changes for repossession."""
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    reason = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Status History"
        verbose_name_plural = "Status Histories"
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.repossession.repossession_number}: {self.old_status} → {self.new_status}"


class RepossessionNotice(models.Model):
    """Legal notices sent to clients."""
    
    NOTICE_TYPE_CHOICES = [
        ('FIRST_NOTICE', 'First Notice'),
        ('SECOND_NOTICE', 'Second Notice'),
        ('FINAL_NOTICE', 'Final Notice'),
        ('LEGAL_NOTICE', 'Legal Notice'),
        ('COURT_SUMMONS', 'Court Summons'),
    ]
    
    DELIVERY_METHOD_CHOICES = [
        ('EMAIL', 'Email'),
        ('POST', 'Postal Mail'),
        ('HAND_DELIVERY', 'Hand Delivery'),
        ('SMS', 'SMS'),
        ('COURIER', 'Courier'),
    ]
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='notices'
    )
    
    notice_type = models.CharField(max_length=20, choices=NOTICE_TYPE_CHOICES)
    notice_date = models.DateField(default=timezone.now)
    
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES)
    delivery_address = models.TextField()
    
    tracking_number = models.CharField(max_length=100, blank=True)
    
    delivered = models.BooleanField(default=False)
    delivery_date = models.DateField(null=True, blank=True)
    received_by = models.CharField(max_length=200, blank=True)
    
    # Response deadline
    response_deadline = models.DateField(null=True, blank=True)
    response_received = models.BooleanField(default=False)
    response_date = models.DateField(null=True, blank=True)
    response_notes = models.TextField(blank=True)
    
    # Content
    content = models.TextField(help_text="Notice content/message")
    
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Repossession Notice"
        verbose_name_plural = "Repossession Notices"
        ordering = ['-notice_date']
    
    def __str__(self):
        return f"{self.get_notice_type_display()} - {self.repossession.repossession_number}"
    
    def is_overdue(self):
        """Check if response is overdue."""
        if self.response_deadline and not self.response_received:
            return date.today() > self.response_deadline
        return False


class RepossessionContact(models.Model):
    """Track contact attempts with client."""
    
    CONTACT_METHOD_CHOICES = [
        ('PHONE', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('VISIT', 'In-Person Visit'),
        ('LETTER', 'Letter'),
    ]
    
    OUTCOME_CHOICES = [
        ('SUCCESSFUL', 'Successful Contact'),
        ('NO_ANSWER', 'No Answer'),
        ('REFUSED', 'Refused to Engage'),
        ('PARTIAL', 'Partial Information'),
        ('VOICEMAIL', 'Left Voicemail'),
        ('PROMISE_TO_PAY', 'Promise to Pay'),
        ('OTHER', 'Other'),
    ]
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    
    contact_date = models.DateTimeField(default=timezone.now)
    contact_method = models.CharField(max_length=20, choices=CONTACT_METHOD_CHOICES)
    
    contacted_person = models.CharField(
        max_length=200,
        help_text="Name of person contacted"
    )
    
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    
    discussion_summary = models.TextField()
    next_action = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Client Contact"
        verbose_name_plural = "Client Contacts"
        ordering = ['-contact_date']
    
    def __str__(self):
        return f"{self.get_contact_method_display()} - {self.contact_date.strftime('%Y-%m-%d')}"


class RepossessionRecoveryAttempt(models.Model):
    """Track vehicle recovery attempts."""
    
    ATTEMPT_RESULT_CHOICES = [
        ('SUCCESSFUL', 'Vehicle Recovered'),
        ('NOT_FOUND', 'Vehicle Not Found'),
        ('ACCESS_DENIED', 'Access Denied'),
        ('CONFRONTATION', 'Confrontation Occurred'),
        ('POLICE_CALLED', 'Police Involvement'),
        ('POSTPONED', 'Attempt Postponed'),
        ('OTHER', 'Other'),
    ]
    
    repossession = models.ForeignKey(
        Repossession,
        on_delete=models.CASCADE,
        related_name='recovery_attempts'
    )
    
    attempt_date = models.DateTimeField(default=timezone.now)
    location = models.TextField(help_text="Location where attempt was made")
    
    agent_name = models.CharField(max_length=200)
    team_size = models.PositiveIntegerField(default=1)
    
    result = models.CharField(max_length=20, choices=ATTEMPT_RESULT_CHOICES)
    
    details = models.TextField(help_text="Details of the recovery attempt")
    
    police_involved = models.BooleanField(default=False)
    police_report_number = models.CharField(max_length=100, blank=True)
    
    vehicle_condition = models.TextField(
        blank=True,
        help_text="Condition of vehicle if recovered"
    )
    
    cost_incurred = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Recovery Attempt"
        verbose_name_plural = "Recovery Attempts"
        ordering = ['-attempt_date']
    
    def __str__(self):
        return f"Attempt on {self.attempt_date.strftime('%Y-%m-%d')} - {self.get_result_display()}"