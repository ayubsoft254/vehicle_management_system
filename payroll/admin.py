
from django.contrib import admin
from .models import Payroll, EmployeeLoan

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
	list_display = ("employee", "pay_period_start", "pay_period_end", "pay_date", "gross_salary", "total_deductions", "net_salary", "status")
	search_fields = ("employee__username", "employee__first_name", "employee__last_name")
	list_filter = ("status", "pay_period_start", "pay_period_end")

@admin.register(EmployeeLoan)
class EmployeeLoanAdmin(admin.ModelAdmin):
	list_display = ("employee", "loan_type", "principal_amount", "interest_rate", "repayment_months", "status", "application_date")
	search_fields = ("employee__username", "employee__first_name", "employee__last_name")
	list_filter = ("loan_type", "status")
