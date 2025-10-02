"""
Models for the payroll app.
Handles employee management, salary processing, commissions, and deductions.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import calendar

User = get_user_model()


class Employee(models.Model):
    """Employee information and employment details."""
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('TEMPORARY', 'Temporary'),
        ('INTERN', 'Intern'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ON_LEAVE', 'On Leave'),
        ('SUSPENDED', 'Suspended'),
        ('TERMINATED', 'Terminated'),
        ('RESIGNED', 'Resigned'),
    ]
    
    # User Link
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    
    # Personal Information
    employee_id = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    national_id = models.CharField(max_length=50, unique=True)
    
    # Employment Details
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    job_title = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    hire_date = models.DateField()
    termination_date = models.DateField(null=True, blank=True)
    
    # Banking Information
    bank_name = models.CharField(max_length=100)
    bank_account_number = models.CharField(max_length=50)
    bank_branch = models.CharField(max_length=100, blank=True)
    
    # Tax Information
    tax_identification_number = models.CharField(max_length=50, blank=True)
    pension_number = models.CharField(max_length=50, blank=True)
    insurance_number = models.CharField(max_length=50, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=20)
    emergency_contact_relationship = models.CharField(max_length=50)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ['employee_id']
        indexes = [
            models.Index(fields=['status', 'employment_type']),
            models.Index(fields=['department', 'job_title']),
        ]
    
    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name()}"
    
    def save(self, *args, **kwargs):
        """Generate employee ID if not exists."""
        if not self.employee_id:
            # Generate ID: EMP-YYYY-XXX
            from datetime import datetime
            year = datetime.now().year
            prefix = f"EMP-{year}"
            
            last_employee = Employee.objects.filter(
                employee_id__startswith=prefix
            ).order_by('-employee_id').first()
            
            if last_employee:
                last_num = int(last_employee.employee_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.employee_id = f"{prefix}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def get_full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    def get_tenure_years(self):
        """Calculate years of service."""
        if self.termination_date:
            end_date = self.termination_date
        else:
            end_date = date.today()
        
        years = (end_date - self.hire_date).days / 365.25
        return round(years, 2)
    
    def is_active(self):
        """Check if employee is active."""
        return self.status == 'ACTIVE'


class SalaryStructure(models.Model):
    """Employee salary structure with allowances and benefits."""
    
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='salary_structure'
    )
    
    # Basic Salary
    basic_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='KES')
    
    # Allowances
    housing_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    transport_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    medical_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    meal_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    other_allowances = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Commission Structure
    commission_enabled = models.BooleanField(default=False)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Commission percentage"
    )
    
    # Overtime
    overtime_enabled = models.BooleanField(default=False)
    overtime_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Rate per hour"
    )
    
    # Effective Date
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Salary Structure"
        verbose_name_plural = "Salary Structures"
        ordering = ['-effective_from']
    
    def __str__(self):
        return f"Salary Structure for {self.employee.get_full_name()}"
    
    def calculate_gross_salary(self):
        """Calculate total gross salary including all allowances."""
        gross = (
            self.basic_salary +
            self.housing_allowance +
            self.transport_allowance +
            self.medical_allowance +
            self.meal_allowance +
            self.other_allowances
        )
        return gross
    
    def is_active(self):
        """Check if salary structure is currently active."""
        today = date.today()
        if self.effective_to:
            return self.effective_from <= today <= self.effective_to
        return self.effective_from <= today


class Commission(models.Model):
    """Sales commissions for employees."""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
        ('REJECTED', 'Rejected'),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='commissions'
    )
    
    # Commission Details
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount commission is calculated from"
    )
    
    # Related Transaction
    related_vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commissions'
    )
    related_client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commissions'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Period
    commission_date = models.DateField()
    payroll_month = models.DateField(help_text="Month this commission will be paid")
    
    # Approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_commissions'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"
        ordering = ['-commission_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['payroll_month', 'status']),
        ]
    
    def __str__(self):
        return f"Commission for {self.employee.get_full_name()} - {self.amount}"
    
    def approve(self, user):
        """Approve commission."""
        if self.status == 'PENDING':
            self.status = 'APPROVED'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save()
            return True
        return False


class Deduction(models.Model):
    """Salary deductions (taxes, loans, insurance, etc.)."""
    
    DEDUCTION_TYPE_CHOICES = [
        ('TAX', 'Income Tax'),
        ('PENSION', 'Pension/Retirement'),
        ('INSURANCE', 'Insurance'),
        ('LOAN', 'Loan Repayment'),
        ('ADVANCE', 'Salary Advance'),
        ('OTHER', 'Other'),
    ]
    
    FREQUENCY_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('ONE_TIME', 'One Time'),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='deductions'
    )
    
    # Deduction Details
    deduction_type = models.CharField(max_length=20, choices=DEDUCTION_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Frequency
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='MONTHLY')
    
    # Period
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_percentage = models.BooleanField(
        default=False,
        help_text="If true, amount is percentage of gross salary"
    )
    
    # Metadata
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Deduction"
        verbose_name_plural = "Deductions"
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'is_active']),
            models.Index(fields=['deduction_type', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.get_deduction_type_display()} - {self.employee.get_full_name()}"
    
    def calculate_deduction_amount(self, gross_salary):
        """Calculate actual deduction amount."""
        if self.is_percentage:
            return (gross_salary * self.amount) / Decimal('100')
        return self.amount
    
    def is_applicable_for_month(self, year, month):
        """Check if deduction applies to given month."""
        if not self.is_active:
            return False
        
        check_date = date(year, month, 1)
        
        if check_date < self.start_date:
            return False
        
        if self.end_date and check_date > self.end_date:
            return False
        
        if self.frequency == 'ONE_TIME':
            return (check_date.year == self.start_date.year and 
                    check_date.month == self.start_date.month)
        
        return True


class PayrollRun(models.Model):
    """Monthly payroll processing run."""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Period
    payroll_month = models.DateField(help_text="First day of payroll month")
    payroll_number = models.CharField(max_length=50, unique=True, editable=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Totals
    total_employees = models.PositiveIntegerField(default=0)
    total_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Processing
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payrolls'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payrolls'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Payment
    payment_date = models.DateField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Payroll Run"
        verbose_name_plural = "Payroll Runs"
        ordering = ['-payroll_month']
        unique_together = ['payroll_month']
    
    def __str__(self):
        return f"{self.payroll_number} - {self.payroll_month.strftime('%B %Y')}"
    
    def save(self, *args, **kwargs):
        """Generate payroll number if not exists."""
        if not self.payroll_number:
            # Generate number: PAY-YYYYMM-XXX
            prefix = f"PAY-{self.payroll_month.strftime('%Y%m')}"
            
            last_payroll = PayrollRun.objects.filter(
                payroll_number__startswith=prefix
            ).order_by('-payroll_number').first()
            
            if last_payroll:
                last_num = int(last_payroll.payroll_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.payroll_number = f"{prefix}-{new_num:03d}"
        
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate total amounts from payslips."""
        payslips = self.payslips.all()
        
        self.total_employees = payslips.count()
        self.total_gross = sum(p.gross_salary for p in payslips)
        self.total_deductions = sum(p.total_deductions for p in payslips)
        self.total_net = sum(p.net_salary for p in payslips)
        
        self.save(update_fields=[
            'total_employees', 'total_gross', 
            'total_deductions', 'total_net'
        ])


class Payslip(models.Model):
    """Individual employee payslip."""
    
    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name='payslips'
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='payslips'
    )
    
    # Earnings
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    meal_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    overtime_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    
    # Deductions
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    pension_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    insurance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    loan_repayment = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    
    # Working Days
    working_days = models.PositiveIntegerField(default=0)
    days_worked = models.PositiveIntegerField(default=0)
    absent_days = models.PositiveIntegerField(default=0)
    
    # Status
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Payslip"
        verbose_name_plural = "Payslips"
        ordering = ['-created_at']
        unique_together = ['payroll_run', 'employee']
        indexes = [
            models.Index(fields=['employee', 'payroll_run']),
        ]
    
    def __str__(self):
        return f"Payslip for {self.employee.get_full_name()} - {self.payroll_run.payroll_month.strftime('%B %Y')}"
    
    def save(self, *args, **kwargs):
        """Calculate totals before saving."""
        # Calculate gross salary
        self.gross_salary = (
            self.basic_salary +
            self.housing_allowance +
            self.transport_allowance +
            self.medical_allowance +
            self.meal_allowance +
            self.other_allowances +
            self.commission_amount +
            self.overtime_amount +
            self.bonus_amount
        )
        
        # Calculate total deductions
        self.total_deductions = (
            self.income_tax +
            self.pension_contribution +
            self.insurance_deduction +
            self.loan_repayment +
            self.other_deductions
        )
        
        # Calculate net salary
        self.net_salary = self.gross_salary - self.total_deductions
        
        super().save(*args, **kwargs)


class Attendance(models.Model):
    """Daily employee attendance tracking."""
    
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('HALF_DAY', 'Half Day'),
        ('ON_LEAVE', 'On Leave'),
        ('HOLIDAY', 'Holiday'),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    
    attendance_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    
    hours_worked = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Attendance"
        verbose_name_plural = "Attendance Records"
        ordering = ['-attendance_date']
        unique_together = ['employee', 'attendance_date']
        indexes = [
            models.Index(fields=['employee', 'attendance_date']),
            models.Index(fields=['status', 'attendance_date']),
        ]
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.attendance_date}"


class Leave(models.Model):
    """Employee leave management."""
    
    LEAVE_TYPE_CHOICES = [
        ('ANNUAL', 'Annual Leave'),
        ('SICK', 'Sick Leave'),
        ('MATERNITY', 'Maternity Leave'),
        ('PATERNITY', 'Paternity Leave'),
        ('UNPAID', 'Unpaid Leave'),
        ('BEREAVEMENT', 'Bereavement Leave'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.PositiveIntegerField()
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Leave"
        verbose_name_plural = "Leave Requests"
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_leave_type_display()}"


class Loan(models.Model):
    """Employee loans and repayment tracking."""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='loans'
    )
    
    loan_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    monthly_repayment = models.DecimalField(max_digits=10, decimal_places=2)
    total_repayable = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    amount_repaid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    
    disbursement_date = models.DateField()
    repayment_start_date = models.DateField()
    expected_completion_date = models.DateField()
    actual_completion_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_loans'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    purpose = models.TextField()
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Loan"
        verbose_name_plural = "Loans"
        ordering = ['-disbursement_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
        ]
    
    def __str__(self):
        return f"Loan for {self.employee.get_full_name()} - {self.loan_amount}"
    
    def save(self, *args, **kwargs):
        """Calculate totals before saving."""
        # Calculate total repayable with interest
        interest_amount = (self.loan_amount * self.interest_rate) / Decimal('100')
        self.total_repayable = self.loan_amount + interest_amount
        
        # Calculate balance
        self.balance = self.total_repayable - self.amount_repaid
        
        super().save(*args, **kwargs)
    
    def get_repayment_percentage(self):
        """Get percentage of loan repaid."""
        if self.total_repayable > 0:
            return (self.amount_repaid / self.total_repayable) * 100
        return 0