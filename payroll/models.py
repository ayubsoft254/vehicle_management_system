from django.db import models
from core.models import User
import uuid

class Payroll(models.Model):
    """Employee payroll records"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payrolls')
    
    # Period
    pay_period_start = models.DateField()
    pay_period_end = models.DateField()
    pay_date = models.DateField()
    
    # Earnings
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions
    tax_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Calculated fields
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    # Status and notes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_payrolls')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payrolls')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-pay_period_end']
        unique_together = ('employee', 'pay_period_start', 'pay_period_end')
    
    def save(self, *args, **kwargs):
        # Calculate derived fields
        overtime_pay = self.overtime_hours * self.overtime_rate
        self.gross_salary = (
            self.basic_salary + overtime_pay + self.commission + 
            self.allowances + self.bonus
        )
        self.total_deductions = (
            self.tax_deduction + self.insurance_deduction + 
            self.loan_deduction + self.other_deductions
        )
        self.net_salary = self.gross_salary - self.total_deductions
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.pay_period_start} to {self.pay_period_end}"

class EmployeeLoan(models.Model):
    """Employee loans and advances"""
    
    LOAN_TYPES = [
        ('salary_advance', 'Salary Advance'),
        ('personal_loan', 'Personal Loan'),
        ('emergency_loan', 'Emergency Loan'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    
    # Loan Details
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPES)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    repayment_months = models.PositiveIntegerField()
    monthly_deduction = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    application_date = models.DateField(auto_now_add=True)
    approval_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField()
    
    # Metadata
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.loan_type}: {self.principal_amount}"
    
    @property
    def total_amount(self):
        interest = (self.principal_amount * self.interest_rate / 100) * (self.repayment_months / 12)
        return self.principal_amount + interest
    
    @property
    def remaining_balance(self):
        # This would need to be calculated based on actual deductions made
        # For now, returning the total amount
        return self.total_amount