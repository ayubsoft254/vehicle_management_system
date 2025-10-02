"""
Views for the payroll app.
Handles employee management, salary processing, and payroll operations.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.db import transaction
from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar

from .models import (
    Employee, SalaryStructure, Commission, Deduction,
    PayrollRun, Payslip, Attendance, Leave, Loan
)
from .forms import (
    EmployeeForm, SalaryStructureForm, CommissionForm, DeductionForm,
    PayrollRunForm, AttendanceForm, LeaveForm, LeaveApprovalForm,
    LoanForm, PayrollSearchForm, BulkAttendanceForm
)


# ============================================================================
# Dashboard and Overview
# ============================================================================

@login_required
def payroll_dashboard(request):
    """Display payroll dashboard with key metrics."""
    # Active employees
    active_employees = Employee.objects.filter(status='ACTIVE').count()
    
    # Current month payroll
    today = date.today()
    current_month = today.replace(day=1)
    
    try:
        current_payroll = PayrollRun.objects.get(payroll_month=current_month)
    except PayrollRun.DoesNotExist:
        current_payroll = None
    
    # Pending approvals
    pending_leaves = Leave.objects.filter(status='PENDING').count()
    pending_loans = Loan.objects.filter(status='PENDING').count()
    pending_commissions = Commission.objects.filter(status='PENDING').count()
    
    # Recent payrolls
    recent_payrolls = PayrollRun.objects.all().order_by('-payroll_month')[:5]
    
    # Monthly payroll trend (last 6 months)
    six_months_ago = current_month - timedelta(days=180)
    payroll_trend = PayrollRun.objects.filter(
        payroll_month__gte=six_months_ago,
        status='COMPLETED'
    ).order_by('payroll_month').values('payroll_month', 'total_net')
    
    context = {
        'active_employees': active_employees,
        'current_payroll': current_payroll,
        'pending_leaves': pending_leaves,
        'pending_loans': pending_loans,
        'pending_commissions': pending_commissions,
        'recent_payrolls': recent_payrolls,
        'payroll_trend': list(payroll_trend),
    }
    
    return render(request, 'payroll/dashboard.html', context)


# ============================================================================
# Employee Management Views
# ============================================================================

@login_required
def employee_list(request):
    """Display list of employees."""
    employees = Employee.objects.all().select_related('user').order_by('employee_id')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        employees = employees.filter(status=status_filter)
    
    # Search
    query = request.GET.get('q')
    if query:
        employees = employees.filter(
            Q(employee_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(job_title__icontains=query) |
            Q(department__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(employees, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'query': query,
    }
    
    return render(request, 'payroll/employee_list.html', context)


@login_required
def employee_detail(request, pk):
    """Display employee details."""
    employee = get_object_or_404(Employee, pk=pk)
    
    # Get salary structure
    try:
        salary_structure = employee.salary_structure
    except SalaryStructure.DoesNotExist:
        salary_structure = None
    
    # Get recent payslips
    recent_payslips = employee.payslips.select_related('payroll_run').order_by('-payroll_run__payroll_month')[:6]
    
    # Get active deductions
    active_deductions = employee.deductions.filter(is_active=True)
    
    # Get recent commissions
    recent_commissions = employee.commissions.order_by('-commission_date')[:10]
    
    # Get active loans
    active_loans = employee.loans.filter(status='ACTIVE')
    
    # Get leave balance (simplified - should be more complex)
    current_year = date.today().year
    leaves_taken = employee.leave_requests.filter(
        status='APPROVED',
        start_date__year=current_year
    ).aggregate(Sum('days_requested'))['days_requested__sum'] or 0
    
    context = {
        'employee': employee,
        'salary_structure': salary_structure,
        'recent_payslips': recent_payslips,
        'active_deductions': active_deductions,
        'recent_commissions': recent_commissions,
        'active_loans': active_loans,
        'leaves_taken': leaves_taken,
        'tenure_years': employee.get_tenure_years(),
    }
    
    return render(request, 'payroll/employee_detail.html', context)


@login_required
def employee_create(request):
    """Create a new employee."""
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.get_full_name()} created successfully.')
            return redirect('payroll:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm()
    
    context = {
        'form': form,
        'title': 'Add New Employee',
    }
    
    return render(request, 'payroll/employee_form.html', context)


@login_required
def employee_update(request, pk):
    """Update employee details."""
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.get_full_name()} updated successfully.')
            return redirect('payroll:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    
    context = {
        'form': form,
        'employee': employee,
        'title': 'Edit Employee',
    }
    
    return render(request, 'payroll/employee_form.html', context)


# ============================================================================
# Salary Structure Views
# ============================================================================

@login_required
def salary_structure_create(request, employee_pk):
    """Create or update salary structure for employee."""
    employee = get_object_or_404(Employee, pk=employee_pk)
    
    try:
        salary_structure = employee.salary_structure
        is_update = True
    except SalaryStructure.DoesNotExist:
        salary_structure = None
        is_update = False
    
    if request.method == 'POST':
        form = SalaryStructureForm(request.POST, instance=salary_structure)
        if form.is_valid():
            structure = form.save(commit=False)
            structure.employee = employee
            structure.save()
            
            action = 'updated' if is_update else 'created'
            messages.success(request, f'Salary structure {action} successfully.')
            return redirect('payroll:employee_detail', pk=employee.pk)
    else:
        form = SalaryStructureForm(instance=salary_structure)
        form.fields['employee'].initial = employee
        form.fields['employee'].widget.attrs['readonly'] = True
    
    context = {
        'form': form,
        'employee': employee,
        'is_update': is_update,
    }
    
    return render(request, 'payroll/salary_structure_form.html', context)


# ============================================================================
# Commission Management Views
# ============================================================================

@login_required
def commission_list(request):
    """Display list of commissions."""
    commissions = Commission.objects.all().select_related(
        'employee', 'approved_by'
    ).order_by('-commission_date')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        commissions = commissions.filter(status=status_filter)
    
    # Filter by employee
    employee_id = request.GET.get('employee')
    if employee_id:
        commissions = commissions.filter(employee_id=employee_id)
    
    # Pagination
    paginator = Paginator(commissions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get summary
    summary = commissions.aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'summary': summary,
    }
    
    return render(request, 'payroll/commission_list.html', context)


@login_required
def commission_create(request):
    """Create a new commission."""
    if request.method == 'POST':
        form = CommissionForm(request.POST)
        if form.is_valid():
            commission = form.save()
            messages.success(request, f'Commission of {commission.amount} created.')
            return redirect('payroll:commission_list')
    else:
        form = CommissionForm()
    
    context = {
        'form': form,
        'title': 'Add Commission',
    }
    
    return render(request, 'payroll/commission_form.html', context)


@login_required
@require_http_methods(["POST"])
def commission_approve(request, pk):
    """Approve a commission."""
    commission = get_object_or_404(Commission, pk=pk)
    
    if commission.approve(request.user):
        messages.success(request, f'Commission approved.')
        return JsonResponse({
            'success': True,
            'message': 'Commission approved successfully.'
        })
    
    return JsonResponse({
        'error': 'Cannot approve commission',
        'message': 'Commission is not pending.'
    }, status=400)


# ============================================================================
# Deduction Management Views
# ============================================================================

@login_required
def deduction_list(request):
    """Display list of deductions."""
    deductions = Deduction.objects.all().select_related('employee').order_by('-start_date')
    
    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter:
        deductions = deductions.filter(deduction_type=type_filter)
    
    # Filter by employee
    employee_id = request.GET.get('employee')
    if employee_id:
        deductions = deductions.filter(employee_id=employee_id)
    
    # Filter active only
    if request.GET.get('active') == 'true':
        deductions = deductions.filter(is_active=True)
    
    # Pagination
    paginator = Paginator(deductions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'type_filter': type_filter,
    }
    
    return render(request, 'payroll/deduction_list.html', context)


@login_required
def deduction_create(request):
    """Create a new deduction."""
    if request.method == 'POST':
        form = DeductionForm(request.POST)
        if form.is_valid():
            deduction = form.save()
            messages.success(request, f'Deduction created successfully.')
            return redirect('payroll:deduction_list')
    else:
        form = DeductionForm()
    
    context = {
        'form': form,
        'title': 'Add Deduction',
    }
    
    return render(request, 'payroll/deduction_form.html', context)


# ============================================================================
# Payroll Run Views
# ============================================================================

@login_required
def payroll_run_list(request):
    """Display list of payroll runs."""
    form = PayrollSearchForm(request.GET or None)
    
    payroll_runs = PayrollRun.objects.all().select_related(
        'processed_by', 'approved_by'
    ).order_by('-payroll_month')
    
    # Apply filters
    if form.is_valid():
        month_from = form.cleaned_data.get('month_from')
        if month_from:
            payroll_runs = payroll_runs.filter(payroll_month__gte=month_from)
        
        month_to = form.cleaned_data.get('month_to')
        if month_to:
            payroll_runs = payroll_runs.filter(payroll_month__lte=month_to)
        
        status = form.cleaned_data.get('status')
        if status:
            payroll_runs = payroll_runs.filter(status=status)
    
    # Pagination
    paginator = Paginator(payroll_runs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
    }
    
    return render(request, 'payroll/payroll_run_list.html', context)


@login_required
def payroll_run_detail(request, pk):
    """Display payroll run details."""
    payroll_run = get_object_or_404(PayrollRun, pk=pk)
    
    # Get payslips
    payslips = payroll_run.payslips.select_related('employee').order_by('employee__employee_id')
    
    # Department breakdown
    dept_breakdown = payslips.values('employee__department').annotate(
        count=Count('id'),
        total=Sum('net_salary')
    ).order_by('employee__department')
    
    # Pagination
    paginator = Paginator(payslips, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'payroll_run': payroll_run,
        'page_obj': page_obj,
        'dept_breakdown': dept_breakdown,
    }
    
    return render(request, 'payroll/payroll_run_detail.html', context)


@login_required
def payroll_run_create(request):
    """Create a new payroll run."""
    if request.method == 'POST':
        form = PayrollRunForm(request.POST)
        if form.is_valid():
            payroll_run = form.save()
            messages.success(request, f'Payroll run created for {payroll_run.payroll_month.strftime("%B %Y")}.')
            return redirect('payroll:payroll_run_process', pk=payroll_run.pk)
    else:
        # Default to current month
        form = PayrollRunForm(initial={'payroll_month': date.today().replace(day=1)})
    
    context = {
        'form': form,
        'title': 'Create Payroll Run',
    }
    
    return render(request, 'payroll/payroll_run_form.html', context)


@login_required
def payroll_run_process(request, pk):
    """Process payroll run - generate payslips."""
    payroll_run = get_object_or_404(PayrollRun, pk=pk)
    
    if payroll_run.status not in ['DRAFT', 'PROCESSING']:
        messages.error(request, 'This payroll has already been processed.')
        return redirect('payroll:payroll_run_detail', pk=payroll_run.pk)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Mark as processing
                payroll_run.status = 'PROCESSING'
                payroll_run.save()
                
                # Get active employees
                employees = Employee.objects.filter(status='ACTIVE').select_related('salary_structure')
                
                for employee in employees:
                    # Skip if no salary structure
                    if not hasattr(employee, 'salary_structure'):
                        continue
                    
                    salary = employee.salary_structure
                    
                    # Calculate working days for the month
                    year = payroll_run.payroll_month.year
                    month = payroll_run.payroll_month.month
                    working_days = calendar.monthrange(year, month)[1]
                    
                    # Get attendance for the month
                    attendance_records = employee.attendance_records.filter(
                        attendance_date__year=year,
                        attendance_date__month=month
                    )
                    days_worked = attendance_records.filter(status='PRESENT').count()
                    absent_days = attendance_records.filter(status='ABSENT').count()
                    
                    # Get commissions for the month
                    commissions = employee.commissions.filter(
                        payroll_month=payroll_run.payroll_month,
                        status='APPROVED'
                    )
                    commission_amount = commissions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                    
                    # Get deductions
                    deductions = employee.deductions.filter(is_active=True)
                    
                    income_tax = Decimal('0.00')
                    pension = Decimal('0.00')
                    insurance = Decimal('0.00')
                    loan_repayment = Decimal('0.00')
                    other_deductions_total = Decimal('0.00')
                    
                    gross = salary.calculate_gross_salary()
                    
                    for deduction in deductions:
                        if deduction.is_applicable_for_month(year, month):
                            amount = deduction.calculate_deduction_amount(gross)
                            
                            if deduction.deduction_type == 'TAX':
                                income_tax += amount
                            elif deduction.deduction_type == 'PENSION':
                                pension += amount
                            elif deduction.deduction_type == 'INSURANCE':
                                insurance += amount
                            elif deduction.deduction_type in ['LOAN', 'ADVANCE']:
                                loan_repayment += amount
                            else:
                                other_deductions_total += amount
                    
                    # Create payslip
                    Payslip.objects.create(
                        payroll_run=payroll_run,
                        employee=employee,
                        basic_salary=salary.basic_salary,
                        housing_allowance=salary.housing_allowance,
                        transport_allowance=salary.transport_allowance,
                        medical_allowance=salary.medical_allowance,
                        meal_allowance=salary.meal_allowance,
                        other_allowances=salary.other_allowances,
                        commission_amount=commission_amount,
                        overtime_amount=Decimal('0.00'),  # TODO: Calculate overtime
                        bonus_amount=Decimal('0.00'),  # TODO: Handle bonuses
                        income_tax=income_tax,
                        pension_contribution=pension,
                        insurance_deduction=insurance,
                        loan_repayment=loan_repayment,
                        other_deductions=other_deductions_total,
                        working_days=working_days,
                        days_worked=days_worked,
                        absent_days=absent_days,
                    )
                
                # Update payroll totals
                payroll_run.calculate_totals()
                
                # Mark as completed
                payroll_run.status = 'COMPLETED'
                payroll_run.processed_by = request.user
                payroll_run.processed_at = timezone.now()
                payroll_run.save()
                
                messages.success(
                    request,
                    f'Payroll processed successfully. {payroll_run.total_employees} payslips generated.'
                )
                return redirect('payroll:payroll_run_detail', pk=payroll_run.pk)
        
        except Exception as e:
            messages.error(request, f'Error processing payroll: {str(e)}')
            payroll_run.status = 'DRAFT'
            payroll_run.save()
    
    # Get preview of employees to be processed
    employees = Employee.objects.filter(status='ACTIVE')
    
    context = {
        'payroll_run': payroll_run,
        'employees': employees,
        'employee_count': employees.count(),
    }
    
    return render(request, 'payroll/payroll_run_process.html', context)


@login_required
@require_http_methods(["POST"])
def payroll_run_approve(request, pk):
    """Approve a payroll run."""
    payroll_run = get_object_or_404(PayrollRun, pk=pk)
    
    if payroll_run.status != 'COMPLETED':
        return JsonResponse({
            'error': 'Cannot approve',
            'message': 'Payroll must be completed first.'
        }, status=400)
    
    payroll_run.status = 'APPROVED'
    payroll_run.approved_by = request.user
    payroll_run.approved_at = timezone.now()
    payroll_run.save()
    
    messages.success(request, f'Payroll approved successfully.')
    
    return JsonResponse({
        'success': True,
        'message': 'Payroll approved successfully.'
    })


# ============================================================================
# Payslip Views
# ============================================================================

@login_required
def payslip_detail(request, pk):
    """Display individual payslip."""
    payslip = get_object_or_404(Payslip, pk=pk)
    
    context = {
        'payslip': payslip,
    }
    
    return render(request, 'payroll/payslip_detail.html', context)


@login_required
def payslip_download(request, pk):
    """Download payslip as PDF."""
    payslip = get_object_or_404(Payslip, pk=pk)
    
    # TODO: Generate PDF
    # For now, return simple response
    messages.info(request, 'PDF generation not yet implemented.')
    return redirect('payroll:payslip_detail', pk=pk)


# ============================================================================
# Attendance Views
# ============================================================================

@login_required
def attendance_list(request):
    """Display attendance records."""
    attendance = Attendance.objects.all().select_related('employee').order_by('-attendance_date')
    
    # Filter by date
    date_filter = request.GET.get('date')
    if date_filter:
        attendance = attendance.filter(attendance_date=date_filter)
    
    # Filter by employee
    employee_id = request.GET.get('employee')
    if employee_id:
        attendance = attendance.filter(employee_id=employee_id)
    
    # Pagination
    paginator = Paginator(attendance, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'date_filter': date_filter,
    }
    
    return render(request, 'payroll/attendance_list.html', context)


@login_required
def attendance_mark(request):
    """Mark attendance for employees."""
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance = form.save()
            messages.success(request, 'Attendance marked successfully.')
            return redirect('payroll:attendance_list')
    else:
        form = AttendanceForm(initial={'attendance_date': date.today()})
    
    context = {
        'form': form,
        'title': 'Mark Attendance',
    }
    
    return render(request, 'payroll/attendance_form.html', context)


@login_required
@require_http_methods(["POST"])
def attendance_bulk_mark(request):
    """Mark attendance for multiple employees."""
    form = BulkAttendanceForm(request.POST)
    
    if not form.is_valid():
        messages.error(request, 'Invalid form data.')
        return redirect('payroll:attendance_list')
    
    employee_ids = form.cleaned_data['employee_ids']
    attendance_date = form.cleaned_data['attendance_date']
    status = form.cleaned_data['status']
    
    count = 0
    for emp_id in employee_ids:
        Attendance.objects.update_or_create(
            employee_id=emp_id,
            attendance_date=attendance_date,
            defaults={'status': status}
        )
        count += 1
    
    messages.success(request, f'Attendance marked for {count} employee(s).')
    return redirect('payroll:attendance_list')


# ============================================================================
# Leave Management Views
# ============================================================================

@login_required
def leave_list(request):
    """Display leave requests."""
    leaves = Leave.objects.all().select_related('employee', 'approved_by').order_by('-start_date')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        leaves = leaves.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(leaves, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    
    return render(request, 'payroll/leave_list.html', context)


@login_required
def leave_create(request):
    """Create leave request."""
    if request.method == 'POST':
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save()
            messages.success(request, 'Leave request submitted.')
            return redirect('payroll:leave_list')
    else:
        form = LeaveForm()
    
    context = {
        'form': form,
        'title': 'Request Leave',
    }
    
    return render(request, 'payroll/leave_form.html', context)


@login_required
def leave_approve(request, pk):
    """Approve or reject leave request."""
    leave = get_object_or_404(Leave, pk=pk)
    
    if leave.status != 'PENDING':
        messages.error(request, 'This leave request has already been processed.')
        return redirect('payroll:leave_list')
    
    if request.method == 'POST':
        form = LeaveApprovalForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            
            if action == 'approve':
                leave.status = 'APPROVED'
                leave.approved_by = request.user
                leave.approved_at = timezone.now()
                leave.save()
                messages.success(request, 'Leave request approved.')
            else:
                leave.status = 'REJECTED'
                leave.approved_by = request.user
                leave.approved_at = timezone.now()
                leave.rejection_reason = form.cleaned_data['rejection_reason']
                leave.save()
                messages.success(request, 'Leave request rejected.')
            
            return redirect('payroll:leave_list')
    else:
        form = LeaveApprovalForm()
    
    context = {
        'form': form,
        'leave': leave,
    }
    
    return render(request, 'payroll/leave_approve.html', context)


# ============================================================================
# Loan Management Views
# ============================================================================

@login_required
def loan_list(request):
    """Display employee loans."""
    loans = Loan.objects.all().select_related('employee', 'approved_by').order_by('-disbursement_date')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        loans = loans.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(loans, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    
    return render(request, 'payroll/loan_list.html', context)


@login_required
def loan_create(request):
    """Create loan application."""
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save()
            messages.success(request, 'Loan application submitted.')
            return redirect('payroll:loan_list')
    else:
        form = LoanForm()
    
    context = {
        'form': form,
        'title': 'Apply for Loan',
    }
    
    return render(request, 'payroll/loan_form.html', context)


@login_required
@require_http_methods(["POST"])
def loan_approve(request, pk):
    """Approve a loan."""
    loan = get_object_or_404(Loan, pk=pk)
    
    if loan.status != 'PENDING':
        return JsonResponse({
            'error': 'Cannot approve',
            'message': 'Loan is not pending.'
        }, status=400)
    
    loan.status = 'APPROVED'
    loan.approved_by = request.user
    loan.approved_at = timezone.now()
    loan.save()
    
    messages.success(request, 'Loan approved.')
    
    return JsonResponse({
        'success': True,
        'message': 'Loan approved successfully.'
    })


# ============================================================================
# Reports and Analytics
# ============================================================================

@login_required
def payroll_reports(request):
    """Display payroll reports and analytics."""
    # TODO: Implement comprehensive reporting
    
    context = {
        'title': 'Payroll Reports',
    }
    
    return render(request, 'payroll/reports.html', context)