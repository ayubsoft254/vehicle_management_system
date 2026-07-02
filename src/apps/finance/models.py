"""
Models for the finance app.
Bank/Cash Account Ledger and Transaction Control Module.

Phase 1: FinancialAccount plus the full ledger/approval/audit/transfer
schema so later phases (transaction entry, approvals, integrations,
reports) don't require further schema churn.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

User = get_user_model()


# ==================== FINANCIAL ACCOUNT ====================

class FinancialAccount(models.Model):
    """A company bank/cash/M-Pesa/other financial account."""

    ACCOUNT_TYPE_CHOICES = [
        ('bank', 'Bank Account'),
        ('mpesa_paybill', 'M-Pesa Paybill'),
        ('mpesa_till', 'M-Pesa Till'),
        ('cash', 'Cash Account'),
        ('mobile_money', 'Mobile Money Account'),
        ('internal_wallet', 'Internal Wallet'),
        ('suspense', 'Suspense Account'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True, help_text='Short unique account code, e.g. DIB-HOZA')
    account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPE_CHOICES, default='bank')

    bank_name = models.CharField(max_length=150, blank=True)
    branch_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    paybill_number = models.CharField(max_length=20, blank=True)
    till_number = models.CharField(max_length=20, blank=True)
    business_shortcode = models.CharField(max_length=20, blank=True)

    currency = models.CharField(max_length=10, default='KES')
    opening_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    opening_balance_date = models.DateField(default=timezone.now)

    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    is_default = models.BooleanField(default=False, help_text='Default account suggested when recording new transactions')
    allow_manual_transactions = models.BooleanField(default=True)
    require_approval = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_accounts_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finance_accounts'
        ordering = ['name']
        verbose_name = 'Financial Account'
        verbose_name_plural = 'Financial Accounts'

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def is_active(self):
        return self.status == 'active'

    def _sum_for(self, status, direction):
        total = self.ledger_transactions.filter(
            status=status, direction=direction
        ).aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')

    def _sum_for_statuses(self, statuses, direction):
        total = self.ledger_transactions.filter(
            status__in=statuses, direction=direction
        ).aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')

    @property
    def approved_credits(self):
        # A 'reversed' transaction still historically happened — it stays in
        # the balance sum, and is separately offset by its own linked
        # reversal entry (also 'approved'). Excluding it here would make the
        # reversal double-subtract instead of netting to zero.
        return self._sum_for_statuses(['approved', 'reversed'], 'credit')

    @property
    def approved_debits(self):
        return self._sum_for_statuses(['approved', 'reversed'], 'debit')

    @property
    def current_balance(self):
        """Opening balance + approved credits - approved debits. Never a stored value."""
        return self.opening_balance + self.approved_credits - self.approved_debits

    @property
    def pending_inflows(self):
        return self._sum_for('pending_approval', 'credit')

    @property
    def pending_outflows(self):
        return self._sum_for('pending_approval', 'debit')

    @property
    def available_balance(self):
        return self.current_balance + self.pending_inflows - self.pending_outflows


# ==================== LEDGER TRANSACTION ====================

class LedgerTransaction(models.Model):
    """A single ledger entry (debit or credit) against a FinancialAccount."""

    DIRECTION_CHOICES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]

    TRANSACTION_TYPE_CHOICES = [
        # Money in
        ('client_vehicle_payment', 'Client Vehicle Payment'),
        ('hire_purchase_instalment', 'Hire Purchase Instalment Payment'),
        ('vehicle_deposit', 'Vehicle Deposit'),
        ('insurance_payment', 'Insurance Payment'),
        ('tracker_payment', 'Tracker Payment'),
        ('clearance_payment', 'Clearance Payment'),
        ('auction_payment', 'Auction Payment'),
        ('mpesa_payment', 'M-Pesa Payment'),
        ('bank_deposit', 'Bank Deposit'),
        ('cash_deposit', 'Cash Deposit'),
        ('manual_credit_adjustment', 'Manual Credit Adjustment'),
        ('internal_transfer_received', 'Internal Transfer Received'),
        # Money out
        ('vehicle_purchase_cost', 'Vehicle Purchase Cost'),
        ('duty_payment', 'Duty Payment'),
        ('shipping_cost', 'Shipping Cost'),
        ('port_charges', 'Port Charges'),
        ('clearing_charges', 'Clearing Charges'),
        ('repair_expense', 'Repair Expense'),
        ('yard_expense', 'Yard Expense'),
        ('broker_commission', 'Broker Commission'),
        ('supplier_payment', 'Supplier Payment'),
        ('tracker_vendor_payment', 'Tracker Vendor Payment'),
        ('insurance_company_payment', 'Insurance Company Payment'),
        ('auctioneer_payment', 'Auctioneer Payment'),
        ('staff_expense', 'Staff-Related Expense'),
        ('bank_withdrawal', 'Bank Withdrawal'),
        ('cash_withdrawal', 'Cash Withdrawal'),
        ('manual_debit_adjustment', 'Manual Debit Adjustment'),
        ('internal_transfer_sent', 'Internal Transfer Sent'),
        # Control
        ('reversal', 'Reversal'),
        ('correction', 'Correction'),
        ('opening_balance_adjustment', 'Opening Balance Adjustment'),
        ('suspense_allocation', 'Suspense Account Allocation'),
        ('bank_charge', 'Bank Charge'),
        ('refund', 'Refund'),
        ('overpayment_allocation', 'Overpayment Allocation'),
    ]

    SOURCE_MODULE_CHOICES = [
        ('payments', 'Payments'),
        ('expenses', 'Expenses'),
        ('vehicles', 'Vehicles'),
        ('clients', 'Clients'),
        ('auctions', 'Auctions'),
        ('repossessions', 'Repossessions'),
        ('insurance', 'Insurance'),
        ('trackers', 'Trackers'),
        ('clearance', 'Clearance'),
        ('payroll', 'Payroll'),
        ('manual', 'Manual Entry'),
        ('transfer', 'Internal Transfer'),
        ('suspense', 'Suspense'),
        ('reconciliation', 'Reconciliation'),
        ('other', 'Other'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('swift', 'SWIFT'),
        ('internal_transfer', 'Internal Transfer'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('edit_requested', 'Edit Requested'),
        ('edited', 'Edited'),
        ('reversed', 'Reversed'),
        ('cancelled', 'Cancelled'),
    ]

    account = models.ForeignKey(
        FinancialAccount, on_delete=models.PROTECT, related_name='ledger_transactions'
    )
    transaction_date = models.DateField(default=timezone.now)
    reference_number = models.CharField(max_length=40, unique=True, editable=False)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    transaction_type = models.CharField(max_length=40, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=10, default='KES')
    source_module = models.CharField(max_length=30, choices=SOURCE_MODULE_CHOICES, default='manual')

    related_client = models.ForeignKey(
        'clients.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_transactions'
    )
    related_vehicle = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_transactions'
    )

    # Generic link for supplier/vendor/auctioneer/insurer/tracker-provider records,
    # since the codebase has no single unified vendor model
    # (JapanSupplier, Broker, TrackerAgent, ClearingAgent, InsuranceAgent all differ).
    related_party_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    related_party_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_party = GenericForeignKey('related_party_content_type', 'related_party_object_id')
    related_party_label = models.CharField(
        max_length=200, blank=True,
        help_text='Free-text supplier/vendor name, used when no linked record applies'
    )

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    description = models.TextField(blank=True)
    supporting_document = models.FileField(
        upload_to='finance/supporting_documents/%Y/%m/', null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_transactions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_transactions_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    is_reversal = models.BooleanField(default=False)
    is_correction = models.BooleanField(default=False)
    original_transaction = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_entries'
    )

    edit_reason = models.TextField(blank=True)
    reversal_reason = models.TextField(blank=True)
    correction_reason = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finance_ledger_transactions'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['related_party_content_type', 'related_party_object_id']),
        ]
        verbose_name = 'Ledger Transaction'
        verbose_name_plural = 'Ledger Transactions'

    def __str__(self):
        return f"{self.reference_number} - {self.get_transaction_type_display()} ({self.amount})"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        super().save(*args, **kwargs)

    def _generate_reference_number(self):
        today = timezone.now().strftime('%Y%m%d')
        prefix = f"TXN-{today}-"
        last = (
            LedgerTransaction.objects.filter(reference_number__startswith=prefix)
            .order_by('-reference_number').first()
        )
        next_seq = 1
        if last:
            try:
                next_seq = int(last.reference_number.rsplit('-', 1)[-1]) + 1
            except ValueError:
                next_seq = 1
        return f"{prefix}{next_seq:04d}"


# ==================== APPROVAL & AUDIT ====================

class TransactionApproval(models.Model):
    """History of every approval action taken on a LedgerTransaction."""

    ACTION_CHOICES = [
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('edit_requested', 'Edit Requested'),
    ]

    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.CASCADE, related_name='approvals'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actioned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='finance_transaction_actions'
    )
    actioned_at = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True)

    class Meta:
        db_table = 'finance_transaction_approvals'
        ordering = ['-actioned_at']
        verbose_name = 'Transaction Approval'
        verbose_name_plural = 'Transaction Approvals'

    def __str__(self):
        return f"{self.transaction.reference_number} - {self.get_action_display()}"


class TransactionAuditTrail(models.Model):
    """Append-only audit trail of every change made to a LedgerTransaction."""

    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('reverse', 'Reverse'),
        ('correct', 'Correct'),
        ('cancel', 'Cancel'),
    ]

    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.CASCADE, related_name='audit_trail'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='finance_audit_entries'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'finance_transaction_audit_trail'
        ordering = ['-changed_at']
        verbose_name = 'Transaction Audit Trail Entry'
        verbose_name_plural = 'Transaction Audit Trail'

    def __str__(self):
        return f"{self.transaction.reference_number} - {self.get_action_display()} @ {self.changed_at}"


# ==================== INTERNAL TRANSFERS ====================

class InternalTransfer(models.Model):
    """Groups the linked debit/credit LedgerTransaction pair for a transfer between accounts."""

    STATUS_CHOICES = [
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    transfer_reference = models.CharField(max_length=40, unique=True, editable=False)
    from_account = models.ForeignKey(FinancialAccount, on_delete=models.PROTECT, related_name='transfers_out')
    to_account = models.ForeignKey(FinancialAccount, on_delete=models.PROTECT, related_name='transfers_in')
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )
    transfer_date = models.DateField(default=timezone.now)

    debit_transaction = models.OneToOneField(
        LedgerTransaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfer_debit_entry'
    )
    credit_transaction = models.OneToOneField(
        LedgerTransaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfer_credit_entry'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='finance_transfers_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_transfers_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'finance_internal_transfers'
        ordering = ['-transfer_date', '-created_at']
        verbose_name = 'Internal Transfer'
        verbose_name_plural = 'Internal Transfers'

    def __str__(self):
        return f"{self.transfer_reference}: {self.from_account} -> {self.to_account} ({self.amount})"

    def save(self, *args, **kwargs):
        if not self.transfer_reference:
            self.transfer_reference = self._generate_transfer_reference()
        super().save(*args, **kwargs)

    def _generate_transfer_reference(self):
        today = timezone.now().strftime('%Y%m%d')
        prefix = f"TRF-{today}-"
        last = (
            InternalTransfer.objects.filter(transfer_reference__startswith=prefix)
            .order_by('-transfer_reference').first()
        )
        next_seq = 1
        if last:
            try:
                next_seq = int(last.transfer_reference.rsplit('-', 1)[-1]) + 1
            except ValueError:
                next_seq = 1
        return f"{prefix}{next_seq:04d}"


# ==================== RECONCILIATION ====================

class AccountReconciliation(models.Model):
    """A reconciliation of an account's book balance against an external statement."""

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='reconciliations')
    reconciliation_date = models.DateField(default=timezone.now)
    statement_balance = models.DecimalField(max_digits=14, decimal_places=2)
    book_balance = models.DecimalField(max_digits=14, decimal_places=2)
    difference = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    notes = models.TextField(blank=True)
    reconciled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_reconciliations'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finance_account_reconciliations'
        ordering = ['-reconciliation_date']
        verbose_name = 'Account Reconciliation'
        verbose_name_plural = 'Account Reconciliations'

    def __str__(self):
        return f"{self.account.name} reconciliation @ {self.reconciliation_date}"

    def save(self, *args, **kwargs):
        self.difference = self.statement_balance - self.book_balance
        super().save(*args, **kwargs)


# ==================== SUSPENSE ====================

class SuspenseTransaction(models.Model):
    """Tracks an unmatched payment posted to a suspense account until it is allocated."""

    transaction = models.OneToOneField(
        LedgerTransaction, on_delete=models.CASCADE, related_name='suspense_detail'
    )
    is_allocated = models.BooleanField(default=False)

    allocated_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    allocated_object_id = models.PositiveIntegerField(null=True, blank=True)
    allocated_to = GenericForeignKey('allocated_content_type', 'allocated_object_id')

    allocated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_suspense_allocations'
    )
    allocated_at = models.DateTimeField(null=True, blank=True)
    allocation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finance_suspense_transactions'
        ordering = ['-created_at']
        verbose_name = 'Suspense Transaction'
        verbose_name_plural = 'Suspense Transactions'

    def __str__(self):
        status = 'Allocated' if self.is_allocated else 'Unallocated'
        return f"{self.transaction.reference_number} - {status}"


# ==================== PAYMENT ALLOCATION ====================

class PaymentAllocation(models.Model):
    """Links a client-payment LedgerTransaction to the instalment(s) it paid off."""

    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.CASCADE, related_name='payment_allocations'
    )
    payment_schedule = models.ForeignKey(
        'payments.PaymentSchedule', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_allocations'
    )
    amount_allocated = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finance_payment_allocations'
        ordering = ['-created_at']
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'

    def __str__(self):
        return f"{self.transaction.reference_number} -> {self.amount_allocated}"
