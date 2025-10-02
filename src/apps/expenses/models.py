"""
Models for the expenses app.
Handles expense tracking, categories, approvals, and reimbursements.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class ExpenseCategory(models.Model):
    """Categories for organizing expenses."""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=20, unique=True, help_text="Accounting code")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)
    requires_receipt = models.BooleanField(
        default=True,
        help_text="Whether receipts are mandatory for this category"
    )
    requires_approval = models.BooleanField(
        default=True,
        help_text="Whether expenses need approval"
    )
    budget_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monthly budget limit for this category"
    )
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class (e.g., fa-fuel)")
    color = models.CharField(max_length=7, default="#6c757d", help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Expense Category"
        verbose_name_plural = "Expense Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_full_path(self):
        """Get full category path (Parent > Child)."""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_total_expenses(self, start_date=None, end_date=None):
        """Calculate total expenses for this category."""
        expenses = self.expenses.filter(status='APPROVED')
        
        if start_date:
            expenses = expenses.filter(expense_date__gte=start_date)
        if end_date:
            expenses = expenses.filter(expense_date__lte=end_date)
        
        return expenses.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    def is_over_budget(self, month=None, year=None):
        """Check if category is over budget for given month."""
        if not self.budget_limit:
            return False
        
        if not month or not year:
            now = timezone.now()
            month = now.month
            year = now.year
        
        from datetime import date
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        total = self.get_total_expenses(start_date, end_date)
        return total > self.budget_limit


class Expense(models.Model):
    """Main expense record."""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Credit/Debit Card'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHECK', 'Check'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    
    # Financial Details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='KES')
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )
    
    # Date and Payment
    expense_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    vendor_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    
    # Relationships
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='submitted_expenses'
    )
    related_vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    related_client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    
    # Status and Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Reimbursement
    is_reimbursable = models.BooleanField(default=True)
    reimbursed = models.BooleanField(default=False)
    reimbursement_date = models.DateField(null=True, blank=True)
    reimbursement_reference = models.CharField(max_length=100, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField('ExpenseTag', blank=True, related_name='expenses')
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('YEARLY', 'Yearly'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'expense_date']),
            models.Index(fields=['submitted_by', 'status']),
            models.Index(fields=['category', 'expense_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        """Calculate total amount before saving."""
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)
    
    def approve(self, user):
        """Approve the expense."""
        if self.status == 'SUBMITTED':
            self.status = 'APPROVED'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save()
            return True
        return False
    
    def reject(self, user, reason):
        """Reject the expense."""
        if self.status == 'SUBMITTED':
            self.status = 'REJECTED'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def mark_as_paid(self):
        """Mark expense as paid."""
        if self.status == 'APPROVED':
            self.status = 'PAID'
            if self.is_reimbursable:
                self.reimbursed = True
                self.reimbursement_date = timezone.now().date()
            self.save()
            return True
        return False
    
    def submit_for_approval(self):
        """Submit expense for approval."""
        if self.status == 'DRAFT':
            self.status = 'SUBMITTED'
            self.save()
            return True
        return False
    
    def can_edit(self, user):
        """Check if user can edit this expense."""
        return (self.submitted_by == user and 
                self.status in ['DRAFT', 'REJECTED'])
    
    def can_delete(self, user):
        """Check if user can delete this expense."""
        return (self.submitted_by == user and 
                self.status in ['DRAFT', 'REJECTED'])
    
    def get_tax_percentage(self):
        """Calculate tax as percentage of amount."""
        if self.amount > 0:
            return (self.tax_amount / self.amount) * 100
        return 0


class ExpenseReceipt(models.Model):
    """Receipt/attachment for expenses."""
    
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    file = models.FileField(upload_to='expenses/receipts/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    file_type = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Expense Receipt"
        verbose_name_plural = "Expense Receipts"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Receipt for {self.expense.title}"
    
    def get_file_size_display(self):
        """Return human-readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


class ExpenseApprovalWorkflow(models.Model):
    """Approval workflow for expenses."""
    
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='approval_workflow'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='expense_approvals'
    )
    level = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    comments = models.TextField(blank=True)
    actioned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Expense Approval"
        verbose_name_plural = "Expense Approvals"
        ordering = ['level', 'created_at']
        unique_together = ['expense', 'approver', 'level']
    
    def __str__(self):
        return f"Approval Level {self.level} for {self.expense.title}"


class ExpenseReport(models.Model):
    """Expense report for grouping multiple expenses."""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_number = models.CharField(max_length=50, unique=True, editable=False)
    
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='expense_reports'
    )
    
    start_date = models.DateField()
    end_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expense_reports'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Expense Report"
        verbose_name_plural = "Expense Reports"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        """Generate report number if not exists."""
        if not self.report_number:
            # Generate report number: ER-YYYYMM-XXX
            from datetime import datetime
            prefix = f"ER-{datetime.now().strftime('%Y%m')}"
            last_report = ExpenseReport.objects.filter(
                report_number__startswith=prefix
            ).order_by('-report_number').first()
            
            if last_report:
                last_num = int(last_report.report_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.report_number = f"{prefix}-{new_num:03d}"
        
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Calculate total from associated expenses."""
        total = self.expenses.filter(
            status='APPROVED'
        ).aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return total
    
    def add_expenses(self, expense_ids):
        """Add expenses to this report."""
        from django.core.exceptions import ValidationError
        
        expenses = Expense.objects.filter(id__in=expense_ids)
        
        # Validate expenses are in date range
        for expense in expenses:
            if not (self.start_date <= expense.expense_date <= self.end_date):
                raise ValidationError(
                    f"Expense {expense.title} is outside report date range"
                )
        
        self.expenses.add(*expenses)
        self.calculate_total()


class ExpenseReportItem(models.Model):
    """Link between expense reports and expenses."""
    
    report = models.ForeignKey(
        ExpenseReport,
        on_delete=models.CASCADE,
        related_name='items'
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='report_items'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Report Item"
        verbose_name_plural = "Report Items"
        unique_together = ['report', 'expense']
    
    def __str__(self):
        return f"{self.expense.title} in {self.report.report_number}"


class ExpenseTag(models.Model):
    """Tags for categorizing expenses."""
    
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6c757d")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Expense Tag"
        verbose_name_plural = "Expense Tags"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class RecurringExpense(models.Model):
    """Template for recurring expenses."""
    
    FREQUENCY_CHOICES = [
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='recurring_expenses'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    submitted_by = models.ForeignKey(User, on_delete=models.PROTECT)
    
    is_active = models.BooleanField(default=True)
    last_generated = models.DateField(null=True, blank=True)
    
    vendor_name = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=Expense.PAYMENT_METHOD_CHOICES
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Recurring Expense"
        verbose_name_plural = "Recurring Expenses"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_frequency_display()})"
    
    def generate_expense(self):
        """Generate an expense from this recurring template."""
        expense = Expense.objects.create(
            title=self.title,
            description=self.description,
            category=self.category,
            amount=self.amount,
            currency=self.currency,
            expense_date=timezone.now().date(),
            payment_method=self.payment_method,
            vendor_name=self.vendor_name,
            submitted_by=self.submitted_by,
            is_recurring=True,
            recurring_frequency=self.frequency,
            status='DRAFT'
        )
        
        self.last_generated = timezone.now().date()
        self.save()
        
        return expense