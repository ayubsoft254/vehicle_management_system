"""
Forms for the payroll app.
Handles employee management, salary processing, and payroll operations.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    Employee, SalaryStructure, Commission, Deduction,
    PayrollRun, Payslip, Attendance, Leave, Loan
)

User = get_user_model()


class EmployeeForm(forms.ModelForm):
    """Form for creating and editing employees."""

    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'middle_name', 'date_of_birth',
            'phone_number', 'email', 'national_id', 'employment_type', 'status',
            'job_title', 'hire_date', 'termination_date',
            'bank_name', 'bank_account_number', 'bank_branch',
            'tax_identification_number', 'pension_number', 'insurance_number',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle name (optional)'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job title'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'termination_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank name'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Account number'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Branch (optional)'}),
            'tax_identification_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'KRA PIN'}),
            'pension_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NSSF number'}),
            'insurance_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NHIF number'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency contact name'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency contact phone'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Relationship'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address line 2 (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State/County'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


class SalaryStructureForm(forms.ModelForm):
    """Form for managing employee salary structure."""

    class Meta:
        model = SalaryStructure
        fields = [
            'basic_salary',
            'housing_allowance', 'transport_allowance', 'medical_allowance',
            'meal_allowance', 'other_allowances',
            'commission_enabled', 'commission_amount',
            'overtime_enabled', 'overtime_rate',
            'effective_from', 'effective_to'
        ]
        widgets = {
            'basic_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'housing_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'transport_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'medical_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'meal_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'other_allowances': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'commission_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'commission_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'overtime_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'overtime_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'effective_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['effective_to'].required = False
        self.fields['effective_from'].required = False
        # Default effective_from to today if not set
        if not self.instance.pk and not self.initial.get('effective_from'):
            self.initial['effective_from'] = date.today()

    def clean_effective_from(self):
        value = self.cleaned_data.get('effective_from')
        if not value:
            return date.today()
        return value

    def clean(self):
        cleaned_data = super().clean()
        effective_from = cleaned_data.get('effective_from')
        effective_to = cleaned_data.get('effective_to')
        if effective_from and effective_to and effective_to < effective_from:
            raise ValidationError('End date must be after start date.')
        return cleaned_data


class CommissionForm(forms.ModelForm):
    """Form for recording employee commissions."""

    class Meta:
        model = Commission
        fields = ['employee', 'description', 'amount', 'commission_date', 'payroll_month', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Vehicle sale commission — Client X'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'commission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payroll_month': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False


class DeductionForm(forms.ModelForm):
    """Form for managing salary deductions."""
    
    class Meta:
        model = Deduction
        fields = [
            'employee', 'deduction_type', 'description', 'amount',
            'frequency', 'is_percentage', 'start_date', 'end_date',
            'is_active', 'reference_number', 'notes'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control select2'}),
            'deduction_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Deduction description'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'is_percentage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reference number'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['end_date'].required = False
        self.fields['reference_number'].required = False
        self.fields['notes'].required = False
    
    def clean(self):
        """Validate deduction dates and amounts."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        is_percentage = cleaned_data.get('is_percentage')
        amount = cleaned_data.get('amount')
        
        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError('End date must be after start date.')
        
        if is_percentage and amount and amount > 100:
            raise ValidationError('Percentage cannot exceed 100%.')
        
        return cleaned_data


class PayrollRunForm(forms.ModelForm):
    """Form for creating payroll runs."""
    
    class Meta:
        model = PayrollRun
        fields = ['payroll_month', 'notes']
        widgets = {
            'payroll_month': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'month'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Payroll notes (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False
    
    def clean_payroll_month(self):
        """Validate payroll month."""
        payroll_month = self.cleaned_data.get('payroll_month')
        
        if payroll_month:
            # Check if payroll already exists for this month
            if PayrollRun.objects.filter(payroll_month=payroll_month).exists():
                raise ValidationError(
                    f'Payroll for {payroll_month.strftime("%B %Y")} already exists.'
                )
            
            # Can't create payroll for future months
            today = date.today()
            if payroll_month > today.replace(day=1):
                raise ValidationError('Cannot create payroll for future months.')
        
        return payroll_month


class AttendanceForm(forms.ModelForm):
    """Form for recording employee attendance."""
    
    class Meta:
        model = Attendance
        fields = [
            'employee', 'attendance_date', 'status',
            'check_in_time', 'check_out_time', 'hours_worked', 'notes'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control select2'}),
            'attendance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'check_in_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hours_worked': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['check_in_time'].required = False
        self.fields['check_out_time'].required = False
        self.fields['notes'].required = False
    
    def clean(self):
        """Validate times."""
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_time')
        check_out = cleaned_data.get('check_out_time')
        
        if check_in and check_out:
            if check_out < check_in:
                raise ValidationError('Check-out time must be after check-in time.')
        
        return cleaned_data


class LeaveForm(forms.ModelForm):
    """Form for leave requests."""
    
    class Meta:
        model = Leave
        fields = [
            'employee', 'leave_type', 'start_date', 'end_date',
            'days_requested', 'reason'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control select2'}),
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'days_requested': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Reason for leave'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise ValidationError('End date must be after start date.')
        # Auto-calculate days_requested if not provided
        if start_date and end_date and not cleaned_data.get('days_requested'):
            cleaned_data['days_requested'] = (end_date - start_date).days + 1
        return cleaned_data


class LeaveApprovalForm(forms.Form):
    """Form for approving/rejecting leave requests."""
    
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for rejection (required if rejecting)'
        })
    )
    
    def clean(self):
        """Validate approval action."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise ValidationError('Reason is required when rejecting leave.')
        
        return cleaned_data


class LoanForm(forms.ModelForm):
    """Form for employee loan applications."""

    # Helper field — not a model field; used only by JS to compute monthly repayment.
    installment_months = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 12',
            'id': 'id_installment_months',
        }),
        label='Number of Months',
    )

    class Meta:
        model = Loan
        fields = [
            'employee', 'loan_amount', 'interest_rate', 'monthly_repayment',
            'disbursement_date', 'repayment_start_date', 'expected_completion_date',
            'purpose', 'notes',
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'loan_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'interest_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': '0.00'}),
            'monthly_repayment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Auto-calculated'}),
            'disbursement_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'repayment_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Purpose of loan'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False
        self.fields['interest_rate'].required = False
        self.fields['installment_months'].required = False

    def clean(self):
        cleaned_data = super().clean()
        disbursement_date = cleaned_data.get('disbursement_date')
        repayment_start_date = cleaned_data.get('repayment_start_date')
        expected_completion_date = cleaned_data.get('expected_completion_date')

        if disbursement_date and repayment_start_date:
            if repayment_start_date < disbursement_date:
                raise ValidationError('Repayment start date must be after disbursement date.')

        if repayment_start_date and expected_completion_date:
            if expected_completion_date < repayment_start_date:
                raise ValidationError('Completion date must be after repayment start date.')

        return cleaned_data


class PayrollSearchForm(forms.Form):
    """Form for searching payroll records."""
    
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(status='ACTIVE'),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'All employees'
        })
    )
    
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Department'
        })
    )
    
    month_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'month'
        })
    )
    
    month_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'month'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(PayrollRun.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        month_from = cleaned_data.get('month_from')
        month_to = cleaned_data.get('month_to')
        
        if month_from and month_to and month_from > month_to:
            raise ValidationError('Start month must be before end month.')
        
        return cleaned_data


class BulkAttendanceForm(forms.Form):
    """Form for bulk attendance marking."""
    
    attendance_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    status = forms.ChoiceField(
        choices=Attendance.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    employee_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_employee_ids(self):
        """Parse employee IDs."""
        ids_str = self.cleaned_data.get('employee_ids', '')
        try:
            ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
            if not ids:
                raise ValidationError('No employees selected.')
            return ids
        except ValueError:
            raise ValidationError('Invalid employee IDs.')