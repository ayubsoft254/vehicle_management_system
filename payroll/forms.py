from django import forms
from .models import Payroll, EmployeeLoan

class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        exclude = ['gross_salary', 'total_deductions', 'net_salary', 'created_by', 'approved_by', 'created_at', 'updated_at']

class EmployeeLoanForm(forms.ModelForm):
    class Meta:
        model = EmployeeLoan
        exclude = ['applied_by', 'approved_by', 'created_at', 'application_date']
