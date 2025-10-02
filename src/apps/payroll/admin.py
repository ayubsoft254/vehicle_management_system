"""
Admin configuration for the payroll app.
Provides comprehensive payroll management interface in Django admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from decimal import Decimal

from .models import (
    Employee, SalaryStructure, Commission, Deduction,
    PayrollRun, Payslip, Attendance, Leave, Loan
)


class SalaryStructureInline(admin.StackedInline):
    """Inline admin for salary structure."""
    model = SalaryStructure
    extra = 0
    max_num = 1
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Salary', {
            'fields': ('basic_salary', 'currency')
        }),
        ('Allowances', {
            'fields': ('housing_allowance', 'transport_allowance', 'medical_allowance', 
                      'meal_allowance', 'other_allowances')
        }),
        ('Commission & Overtime', {
            'fields': ('commission_enabled', 'commission_rate', 'overtime_enabled', 'overtime_rate'),
            'classes': ('collapse',)
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to')
        }),
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Admin interface for employees."""
    
    list_display = (
        'employee_id', 'get_full_name', 'job_title', 'department',
        'employment_type', 'status_badge', 'hire_date', 'tenure_display'
    )
    
    list_filter = (
        'status', 'employment_type', 'department', 
        'hire_date', 'created_at'
    )
    
    search_fields = (
        'employee_id', 'first_name', 'last_name', 'email',
        'national_id', 'job_title', 'department'
    )
    
    readonly_fields = (
        'employee_id', 'created_at', 'updated_at', 
        'tenure_display', 'gross_salary_display'
    )
    
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': (
                'employee_id', 'first_name', 'last_name', 'middle_name',
                'date_of_birth', 'phone_number', 'email', 'national_id'
            )
        }),
        ('Employment Details', {
            'fields': (
                'employment_type', 'status', 'job_title', 'department',
                'hire_date', 'termination_date', 'tenure_display'
            )
        }),
        ('Banking Information', {
            'fields': ('bank_name', 'bank_account_number', 'bank_branch'),
            'classes': ('collapse',)
        }),
        ('Tax Information', {
            'fields': ('tax_identification_number', 'pension_number', 'insurance_number'),
            'classes': ('collapse',)
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name', 'emergency_contact_phone',
                'emergency_contact_relationship'
            ),
            'classes': ('collapse',)
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city',
                'state', 'postal_code', 'country'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [SalaryStructureInline]
    
    date_hierarchy = 'hire_date'
    
    actions = ['activate_employees', 'deactivate_employees', 'export_to_csv']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'ACTIVE': '#28a745',
            'ON_LEAVE': '#ffc107',
            'SUSPENDED': '#dc3545',
            'TERMINATED': '#6c757d',
            'RESIGNED': '#6c757d',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def tenure_display(self, obj):
        """Display years of service."""
        years = obj.get_tenure_years()
        return f"{years} years"
    tenure_display.short_description = 'Tenure'
    
    def gross_salary_display(self, obj):
        """Display gross salary if available."""
        if hasattr(obj, 'salary_structure'):
            return f"{obj.salary_structure.currency} {obj.salary_structure.calculate_gross_salary():,.2f}"
        return '-'
    gross_salary_display.short_description = 'Gross Salary'
    
    @admin.action(description='Activate selected employees')
    def activate_employees(self, request, queryset):
        """Activate employees."""
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f'{updated} employee(s) activated.')
    
    @admin.action(description='Deactivate selected employees')
    def deactivate_employees(self, request, queryset):
        """Deactivate employees."""
        updated = queryset.update(status='SUSPENDED')
        self.message_user(request, f'{updated} employee(s) deactivated.')
    
    @admin.action(description='Export to CSV')
    def export_to_csv(self, request, queryset):
        """Export employees to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="employees.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'Name', 'Job Title', 'Department',
            'Employment Type', 'Status', 'Hire Date', 'Email', 'Phone'
        ])
        
        for emp in queryset:
            writer.writerow([
                emp.employee_id,
                emp.get_full_name(),
                emp.job_title,
                emp.department,
                emp.get_employment_type_display(),
                emp.get_status_display(),
                emp.hire_date.strftime('%Y-%m-%d'),
                emp.email,
                emp.phone_number,
            ])
        
        return response


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    """Admin interface for salary structures."""
    
    list_display = (
        'employee_link', 'basic_salary', 'gross_salary_display',
        'commission_enabled', 'effective_from', 'is_active_display'
    )
    
    list_filter = ('commission_enabled', 'overtime_enabled', 'effective_from')
    
    search_fields = ('employee__employee_id', 'employee__first_name', 'employee__last_name')
    
    readonly_fields = ('created_at', 'updated_at', 'gross_salary_display')
    
    fieldsets = (
        ('Employee', {
            'fields': ('employee',)
        }),
        ('Basic Salary', {
            'fields': ('basic_salary', 'currency', 'gross_salary_display')
        }),
        ('Allowances', {
            'fields': (
                'housing_allowance', 'transport_allowance',
                'medical_allowance', 'meal_allowance', 'other_allowances'
            )
        }),
        ('Commission', {
            'fields': ('commission_enabled', 'commission_rate')
        }),
        ('Overtime', {
            'fields': ('overtime_enabled', 'overtime_rate')
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def gross_salary_display(self, obj):
        """Display calculated gross salary."""
        return f"{obj.currency} {obj.calculate_gross_salary():,.2f}"
    gross_salary_display.short_description = 'Gross Salary'
    
    def is_active_display(self, obj):
        """Show if salary structure is active."""
        if obj.is_active():
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    """Admin interface for commissions."""
    
    list_display = (
        'employee_link', 'description', 'amount', 'commission_rate',
        'status_badge', 'commission_date', 'payroll_month'
    )
    
    list_filter = ('status', 'commission_date', 'payroll_month')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name',
        'employee__last_name', 'description'
    )
    
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Commission Details', {
            'fields': (
                'employee', 'description', 'base_amount',
                'commission_rate', 'amount'
            )
        }),
        ('Related Records', {
            'fields': ('related_vehicle', 'related_client'),
            'classes': ('collapse',)
        }),
        ('Period', {
            'fields': ('commission_date', 'payroll_month')
        }),
        ('Status', {
            'fields': ('status', 'approved_by', 'approved_at')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'commission_date'
    
    actions = ['approve_commissions']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'approved_by')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PENDING': '#ffc107',
            'APPROVED': '#28a745',
            'PAID': '#17a2b8',
            'REJECTED': '#dc3545',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    @admin.action(description='Approve selected commissions')
    def approve_commissions(self, request, queryset):
        """Approve commissions."""
        count = 0
        for commission in queryset.filter(status='PENDING'):
            if commission.approve(request.user):
                count += 1
        self.message_user(request, f'{count} commission(s) approved.')


@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    """Admin interface for deductions."""
    
    list_display = (
        'employee_link', 'deduction_type', 'description',
        'amount_display', 'frequency', 'is_active', 'start_date'
    )
    
    list_filter = ('deduction_type', 'frequency', 'is_active', 'is_percentage')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name',
        'employee__last_name', 'description', 'reference_number'
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Deduction Details', {
            'fields': (
                'employee', 'deduction_type', 'description',
                'amount', 'is_percentage'
            )
        }),
        ('Frequency', {
            'fields': ('frequency', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Reference', {
            'fields': ('reference_number', 'notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'start_date'
    
    actions = ['activate_deductions', 'deactivate_deductions']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def amount_display(self, obj):
        """Display amount with percentage indicator."""
        if obj.is_percentage:
            return f"{obj.amount}%"
        return f"KES {obj.amount:,.2f}"
    amount_display.short_description = 'Amount'
    
    @admin.action(description='Activate selected deductions')
    def activate_deductions(self, request, queryset):
        """Activate deductions."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} deduction(s) activated.')
    
    @admin.action(description='Deactivate selected deductions')
    def deactivate_deductions(self, request, queryset):
        """Deactivate deductions."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} deduction(s) deactivated.')


class PayslipInline(admin.TabularInline):
    """Inline admin for payslips."""
    model = Payslip
    extra = 0
    readonly_fields = (
        'employee', 'gross_salary', 'total_deductions',
        'net_salary', 'is_paid'
    )
    fields = (
        'employee', 'gross_salary', 'total_deductions',
        'net_salary', 'is_paid'
    )
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    """Admin interface for payroll runs."""
    
    list_display = (
        'payroll_number', 'payroll_month_display', 'status_badge',
        'total_employees', 'total_net_display', 'processed_at'
    )
    
    list_filter = ('status', 'payroll_month', 'processed_at')
    
    search_fields = ('payroll_number',)
    
    readonly_fields = (
        'payroll_number', 'total_employees', 'total_gross',
        'total_deductions', 'total_net', 'processed_by',
        'processed_at', 'approved_by', 'approved_at',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Payroll Information', {
            'fields': ('payroll_number', 'payroll_month', 'status')
        }),
        ('Totals', {
            'fields': (
                'total_employees', 'total_gross',
                'total_deductions', 'total_net'
            )
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Payment', {
            'fields': ('payment_date',)
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PayslipInline]
    
    date_hierarchy = 'payroll_month'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('processed_by', 'approved_by')
    
    def payroll_month_display(self, obj):
        """Display formatted payroll month."""
        return obj.payroll_month.strftime('%B %Y')
    payroll_month_display.short_description = 'Month'
    payroll_month_display.admin_order_field = 'payroll_month'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'DRAFT': '#6c757d',
            'PROCESSING': '#ffc107',
            'COMPLETED': '#28a745',
            'APPROVED': '#17a2b8',
            'PAID': '#007bff',
            'CANCELLED': '#dc3545',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_net_display(self, obj):
        """Display formatted net total."""
        return f"KES {obj.total_net:,.2f}"
    total_net_display.short_description = 'Total Net'
    total_net_display.admin_order_field = 'total_net'


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    """Admin interface for payslips."""
    
    list_display = (
        'employee_link', 'payroll_run_link', 'gross_salary',
        'total_deductions', 'net_salary', 'is_paid'
    )
    
    list_filter = ('is_paid', 'payroll_run__payroll_month')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name',
        'employee__last_name', 'payroll_run__payroll_number'
    )
    
    readonly_fields = (
        'gross_salary', 'total_deductions', 'net_salary',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Payslip Information', {
            'fields': ('payroll_run', 'employee')
        }),
        ('Earnings', {
            'fields': (
                'basic_salary', 'housing_allowance', 'transport_allowance',
                'medical_allowance', 'meal_allowance', 'other_allowances',
                'commission_amount', 'overtime_amount', 'bonus_amount',
                'gross_salary'
            )
        }),
        ('Deductions', {
            'fields': (
                'income_tax', 'pension_contribution', 'insurance_deduction',
                'loan_repayment', 'other_deductions', 'total_deductions'
            )
        }),
        ('Net Salary', {
            'fields': ('net_salary',)
        }),
        ('Attendance', {
            'fields': ('working_days', 'days_worked', 'absent_days'),
            'classes': ('collapse',)
        }),
        ('Payment', {
            'fields': ('is_paid', 'payment_date', 'payment_reference'),
            'classes': ('collapse',)
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'payroll_run')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def payroll_run_link(self, obj):
        """Display payroll run as clickable link."""
        url = reverse('admin:payroll_payrollrun_change', args=[obj.payroll_run.pk])
        return format_html('<a href="{}">{}</a>', url, obj.payroll_run.payroll_number)
    payroll_run_link.short_description = 'Payroll Run'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    """Admin interface for attendance."""
    
    list_display = (
        'employee_link', 'attendance_date', 'status_badge',
        'check_in_time', 'check_out_time', 'hours_worked'
    )
    
    list_filter = ('status', 'attendance_date')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name', 'employee__last_name'
    )
    
    date_hierarchy = 'attendance_date'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PRESENT': '#28a745',
            'ABSENT': '#dc3545',
            'LATE': '#ffc107',
            'HALF_DAY': '#17a2b8',
            'ON_LEAVE': '#6c757d',
            'HOLIDAY': '#007bff',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    """Admin interface for leave requests."""
    
    list_display = (
        'employee_link', 'leave_type', 'start_date', 'end_date',
        'days_requested', 'status_badge'
    )
    
    list_filter = ('leave_type', 'status', 'start_date')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name',
        'employee__last_name', 'reason'
    )
    
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')
    
    date_hierarchy = 'start_date'
    
    actions = ['approve_leaves', 'reject_leaves']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'approved_by')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PENDING': '#ffc107',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'CANCELLED': '#6c757d',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    @admin.action(description='Approve selected leave requests')
    def approve_leaves(self, request, queryset):
        """Approve leave requests."""
        count = queryset.filter(status='PENDING').update(
            status='APPROVED',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{count} leave request(s) approved.')
    
    @admin.action(description='Reject selected leave requests')
    def reject_leaves(self, request, queryset):
        """Reject leave requests."""
        count = queryset.filter(status='PENDING').update(
            status='REJECTED',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{count} leave request(s) rejected.')


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    """Admin interface for loans."""
    
    list_display = (
        'employee_link', 'loan_amount', 'monthly_repayment',
        'balance', 'status_badge', 'repayment_progress'
    )
    
    list_filter = ('status', 'disbursement_date')
    
    search_fields = (
        'employee__employee_id', 'employee__first_name',
        'employee__last_name', 'purpose'
    )
    
    readonly_fields = (
        'total_repayable', 'balance', 'approved_by',
        'approved_at', 'created_at', 'updated_at', 'repayment_progress'
    )
    
    date_hierarchy = 'disbursement_date'
    
    actions = ['approve_loans']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'approved_by')
    
    def employee_link(self, obj):
        """Display employee as clickable link."""
        url = reverse('admin:payroll_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.get_full_name())
    employee_link.short_description = 'Employee'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PENDING': '#ffc107',
            'APPROVED': '#17a2b8',
            'ACTIVE': '#28a745',
            'COMPLETED': '#6c757d',
            'REJECTED': '#dc3545',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def repayment_progress(self, obj):
        """Display repayment progress bar."""
        percentage = obj.get_repayment_percentage()
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: #28a745; color: white; '
            'text-align: center; border-radius: 3px; padding: 2px;">{:.0f}%</div></div>',
            percentage, percentage
        )
    repayment_progress.short_description = 'Progress'
    
    @admin.action(description='Approve selected loans')
    def approve_loans(self, request, queryset):
        """Approve loans."""
        count = queryset.filter(status='PENDING').update(
            status='APPROVED',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{count} loan(s) approved.')