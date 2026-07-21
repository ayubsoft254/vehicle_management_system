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

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import inch

from .models import (
    Employee, SalaryStructure, Commission, Deduction,
    PayrollRun, Payslip, Attendance, Leave, Loan
)
from .forms import (
    EmployeeForm, SalaryStructureForm, CommissionForm, DeductionForm,
    PayrollRunForm, AttendanceForm, LeaveForm, LeaveApprovalForm,
    LoanForm, PayrollSearchForm, BulkAttendanceForm
)


def _is_approver(user):
    """
    True for users trusted to approve payroll actions (loans, commissions,
    payroll runs) immediately, and to process loans/advances without going
    through the normal pending-approval queue. Mirrors the same convention
    used for account-level approvals in apps.payments.views._is_approver.
    """
    if user.is_superuser:
        return True
    from apps.permissions.models import RolePermission
    from utils.constants import AccessLevel
    try:
        permission = RolePermission.objects.get(role=user.role, module_name='payroll')
    except RolePermission.DoesNotExist:
        return False
    return permission.access_level == AccessLevel.FULL_ACCESS


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
    all_employees = Employee.objects.all().select_related('user')

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        all_employees = all_employees.filter(status=status_filter)

    # Filter by employment type
    employment_type_filter = request.GET.get('employment_type', '')
    if employment_type_filter:
        all_employees = all_employees.filter(employment_type=employment_type_filter)

    # Search
    query = request.GET.get('search', '').strip()
    if query:
        all_employees = all_employees.filter(
            Q(employee_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(job_title__icontains=query) |
            Q(department__icontains=query)
        )

    all_employees = all_employees.order_by('employee_id')

    # Pagination
    paginator = Paginator(all_employees, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    base_qs = Employee.objects.all()
    context = {
        'employees': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status_filter': status_filter,
        'query': query,
        'total_count': base_qs.count(),
        'active_count': base_qs.filter(status='ACTIVE').count(),
        'on_leave_count': base_qs.filter(status='ON_LEAVE').count(),
        'suspended_count': base_qs.filter(status='SUSPENDED').count(),
        'terminated_count': base_qs.filter(status__in=['TERMINATED', 'RESIGNED']).count(),
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
        'leave_balance': max(0, 21 - leaves_taken),
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
            messages.success(request, f'Employee {employee.get_full_name()} created. Now set up their salary structure.')
            return redirect('payroll:salary_structure_create', employee_pk=employee.pk)
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
        try:
            commissions = commissions.filter(employee_id=int(employee_id))
        except (ValueError, TypeError):
            pass

    # Filter by month (e.g. "2024-01")
    month_filter = request.GET.get('month')
    if month_filter:
        try:
            month_date = datetime.strptime(month_filter, '%Y-%m').date()
            commissions = commissions.filter(
                payroll_month__year=month_date.year,
                payroll_month__month=month_date.month,
            )
        except ValueError:
            pass

    # Pagination
    paginator = Paginator(commissions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_commissions = Commission.objects.all()
    context = {
        'page_obj': page_obj,
        'commissions': page_obj,
        'status_filter': status_filter,
        'is_approver': _is_approver(request.user),
        'month_filter': month_filter,
        'total_amount': all_commissions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'pending_count': all_commissions.filter(status='PENDING').count(),
        'approved_count': all_commissions.filter(status='APPROVED').count(),
        'paid_count': all_commissions.filter(status='PAID').count(),
        'employees': Employee.objects.filter(status='ACTIVE').order_by('first_name'),
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

    if not _is_approver(request.user):
        return JsonResponse({
            'error': 'Not authorized',
            'message': 'You are not authorized to approve commissions.'
        }, status=403)

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

    # Filter by type — template sends 'deduction_type'
    type_filter = request.GET.get('deduction_type') or request.GET.get('type')
    if type_filter:
        deductions = deductions.filter(deduction_type=type_filter)

    # Filter by employee
    employee_search = request.GET.get('employee')
    if employee_search:
        deductions = deductions.filter(
            Q(employee__first_name__icontains=employee_search) |
            Q(employee__last_name__icontains=employee_search) |
            Q(employee__employee_id__icontains=employee_search)
        )

    # Filter active/inactive
    is_active_param = request.GET.get('is_active')
    if is_active_param == 'true':
        deductions = deductions.filter(is_active=True)
    elif is_active_param == 'false':
        deductions = deductions.filter(is_active=False)

    # Pagination
    paginator = Paginator(deductions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_deductions = Deduction.objects.all()
    context = {
        'page_obj': page_obj,
        'deductions': page_obj,
        'type_filter': type_filter,
        'total_deductions': all_deductions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'tax_amount': all_deductions.filter(deduction_type='TAX').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'insurance_amount': all_deductions.filter(deduction_type='INSURANCE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'active_count': all_deductions.filter(is_active=True).count(),
    }

    return render(request, 'payroll/deduction_list.html', context)


@login_required
def deduction_create(request):
    """Create a new deduction."""
    is_approver = _is_approver(request.user)

    if request.method == 'POST':
        form = DeductionForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['deduction_type'] == 'ADVANCE' and not is_approver:
                # Salary advances pay out immediately with no separate
                # approval step, so only an approver (admin) may create one.
                form.add_error(None, 'Only an admin/approver can process salary advances.')
            else:
                deduction = form.save()
                if deduction.deduction_type == 'ADVANCE':
                    messages.success(
                        request,
                        f'Salary advance processed for {deduction.employee.get_full_name()}. '
                        f'Posted to the expense ledger.'
                    )
                else:
                    messages.success(request, 'Deduction created successfully.')
                return redirect('payroll:deduction_list')
    else:
        form = DeductionForm()

    context = {
        'form': form,
        'title': 'Add Deduction',
        'is_approver': is_approver,
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
        'is_approver': _is_approver(request.user),
        'unpaid_count': payslips.filter(is_paid=False).count(),
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


def _compute_payslip_fields(employee, payroll_run):
    """
    Compute every Payslip field for one employee for this payroll run,
    without saving anything. Shared by the process preview (GET) and the
    actual Payslip creation (POST) below so the two can never disagree.
    """
    salary = employee.salary_structure
    year = payroll_run.payroll_month.year
    month = payroll_run.payroll_month.month
    working_days = calendar.monthrange(year, month)[1]

    attendance_records = employee.attendance_records.filter(
        attendance_date__year=year,
        attendance_date__month=month
    )
    days_worked = attendance_records.filter(status='PRESENT').count()
    absent_days = attendance_records.filter(status='ABSENT').count()

    commissions = employee.commissions.filter(
        payroll_month=payroll_run.payroll_month,
        status='APPROVED'
    )
    commission_amount = commissions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

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

    gross_total = gross + commission_amount
    deductions_total = income_tax + pension + insurance + loan_repayment + other_deductions_total

    return {
        'basic_salary': salary.basic_salary,
        'housing_allowance': salary.housing_allowance,
        'transport_allowance': salary.transport_allowance,
        'medical_allowance': salary.medical_allowance,
        'meal_allowance': salary.meal_allowance,
        'other_allowances': salary.other_allowances,
        'commission_amount': commission_amount,
        'income_tax': income_tax,
        'pension_contribution': pension,
        'insurance_deduction': insurance,
        'loan_repayment': loan_repayment,
        'other_deductions': other_deductions_total,
        'working_days': working_days,
        'days_worked': days_worked,
        'absent_days': absent_days,
        'gross_total': gross_total,
        'deductions_total': deductions_total,
        'net_total': gross_total - deductions_total,
    }


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

                    data = _compute_payslip_fields(employee, payroll_run)

                    # Create payslip
                    Payslip.objects.create(
                        payroll_run=payroll_run,
                        employee=employee,
                        basic_salary=data['basic_salary'],
                        housing_allowance=data['housing_allowance'],
                        transport_allowance=data['transport_allowance'],
                        medical_allowance=data['medical_allowance'],
                        meal_allowance=data['meal_allowance'],
                        other_allowances=data['other_allowances'],
                        commission_amount=data['commission_amount'],
                        overtime_amount=Decimal('0.00'),  # TODO: Calculate overtime
                        bonus_amount=Decimal('0.00'),  # TODO: Handle bonuses
                        income_tax=data['income_tax'],
                        pension_contribution=data['pension_contribution'],
                        insurance_deduction=data['insurance_deduction'],
                        loan_repayment=data['loan_repayment'],
                        other_deductions=data['other_deductions'],
                        working_days=data['working_days'],
                        days_worked=data['days_worked'],
                        absent_days=data['absent_days'],
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

    # Build an accurate preview using the exact same calculation the POST
    # above will use, so the numbers shown here never disagree with what
    # actually gets processed.
    employees = Employee.objects.filter(status='ACTIVE').select_related('salary_structure')
    preview_rows = []
    working_days = calendar.monthrange(payroll_run.payroll_month.year, payroll_run.payroll_month.month)[1]
    estimated_gross = Decimal('0.00')
    estimated_deductions = Decimal('0.00')
    ready_count = 0

    for employee in employees:
        if not hasattr(employee, 'salary_structure'):
            preview_rows.append({'employee': employee, 'has_salary': False})
            continue
        data = _compute_payslip_fields(employee, payroll_run)
        estimated_gross += data['gross_total']
        estimated_deductions += data['deductions_total']
        ready_count += 1
        preview_rows.append({
            'employee': employee,
            'has_salary': True,
            'basic_salary': data['basic_salary'],
            'net_estimate': data['net_total'],
        })

    context = {
        'payroll_run': payroll_run,
        'employees': employees,
        'employee_count': employees.count(),
        'ready_count': ready_count,
        'preview_rows': preview_rows,
        'working_days': working_days,
        'estimated_gross': estimated_gross,
        'estimated_deductions': estimated_deductions,
        'estimated_net': estimated_gross - estimated_deductions,
    }

    return render(request, 'payroll/payroll_run_process.html', context)


@login_required
@require_http_methods(["POST"])
def payroll_run_approve(request, pk):
    """Approve a payroll run."""
    payroll_run = get_object_or_404(PayrollRun, pk=pk)

    if not _is_approver(request.user):
        return JsonResponse({
            'error': 'Not authorized',
            'message': 'You are not authorized to approve payroll runs.'
        }, status=403)

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


@login_required
@require_http_methods(["POST"])
def payroll_run_mark_paid(request, pk):
    """
    Mark an approved payroll run as paid. This marks every payslip in the
    run as paid, which posts each employee's net salary into the expense
    ledger (see payslip_post_save -> post_salary_expense).
    """
    payroll_run = get_object_or_404(PayrollRun, pk=pk)

    if not _is_approver(request.user):
        return JsonResponse({
            'error': 'Not authorized',
            'message': 'You are not authorized to mark payroll as paid.'
        }, status=403)

    if payroll_run.status != 'APPROVED':
        return JsonResponse({
            'error': 'Cannot mark paid',
            'message': 'Payroll must be approved before it can be marked as paid.'
        }, status=400)

    payment_reference = request.POST.get('payment_reference', '').strip()
    today = timezone.now().date()

    with transaction.atomic():
        for payslip in payroll_run.payslips.filter(is_paid=False):
            payslip.is_paid = True
            payslip.payment_date = today
            if payment_reference:
                payslip.payment_reference = payment_reference
            payslip.save()

        payroll_run.status = 'PAID'
        payroll_run.payment_date = today
        payroll_run.save()

    messages.success(request, 'Payroll marked as paid. Salaries have been posted to the expense ledger.')

    return JsonResponse({
        'success': True,
        'message': 'Payroll marked as paid and posted to the expense ledger.'
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


def _append_payslip_body(elements, styles, payslip, fmt_money, kpi_table):
    """Shared by the single-payslip PDF and the payroll run's 'Print All' bundle."""
    employee = payslip.employee
    heading = styles['ReportSectionHeading']
    heading.spaceBefore = 8
    heading.spaceAfter = 4

    elements.append(Paragraph(
        f'PAYSLIP — {employee.get_full_name()} ({payslip.payroll_run.payroll_month.strftime("%B %Y")})',
        styles['ReportTitle'],
    ))
    elements.append(Spacer(1, 6))

    elements.append(kpi_table([
        ('Employee', employee.get_full_name()),
        ('Employee ID', employee.employee_id),
        ('Job Title', employee.job_title or '—'),
        ('Payroll Number', payslip.payroll_run.payroll_number),
        ('Payment Period', payslip.payroll_run.payroll_month.strftime('%B %Y')),
        ('Working / Worked Days', f'{payslip.working_days} / {payslip.days_worked}'),
    ], col_widths=[2.6 * inch, 2.6 * inch]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph('EARNINGS', heading))
    earning_fields = [
        ('Basic Salary', payslip.basic_salary),
        ('Housing Allowance', payslip.housing_allowance),
        ('Transport Allowance', payslip.transport_allowance),
        ('Medical Allowance', payslip.medical_allowance),
        ('Meal Allowance', payslip.meal_allowance),
        ('Other Allowances', payslip.other_allowances),
        ('Commission', payslip.commission_amount),
        ('Overtime', payslip.overtime_amount),
        ('Bonus', payslip.bonus_amount),
    ]
    earnings_rows = [[label, f'{amount:,.2f}'] for label, amount in earning_fields if amount]
    earnings_rows.append(['GROSS SALARY', f'{payslip.gross_salary:,.2f}'])
    elements.append(kpi_table(earnings_rows, col_widths=[4 * inch, 2 * inch]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph('DEDUCTIONS', heading))
    deduction_fields = [
        ('Income Tax (PAYE)', payslip.income_tax),
        ('Pension (NSSF)', payslip.pension_contribution),
        ('Insurance (NHIF)', payslip.insurance_deduction),
        ('Loan Repayment', payslip.loan_repayment),
        ('Other Deductions', payslip.other_deductions),
    ]
    deduction_rows = [[label, f'{amount:,.2f}'] for label, amount in deduction_fields if amount]
    deduction_rows.append(['TOTAL DEDUCTIONS', f'{payslip.total_deductions:,.2f}'])
    elements.append(kpi_table(deduction_rows, col_widths=[4 * inch, 2 * inch]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f'<b>NET SALARY: {fmt_money(payslip.net_salary)}</b>', styles['ReportSectionHeading']))
    elements.append(Spacer(1, 10))

    if employee.bank_name:
        elements.append(Paragraph('PAYMENT DETAILS', heading))
        elements.append(kpi_table([
            ('Bank Name', employee.bank_name),
            ('Account Number', employee.bank_account_number or '—'),
            ('Payment Status', 'PAID' if payslip.is_paid else 'PENDING'),
        ], col_widths=[2.6 * inch, 2.6 * inch]))
        elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        'This is a computer-generated document. No signature is required.',
        styles['ReportCompanyMeta'],
    ))


@login_required
def payslip_download(request, pk):
    """Download payslip as PDF."""
    from utils.report_kit import build_pdf_response, fmt_money, kpi_table

    payslip = get_object_or_404(Payslip.objects.select_related('employee', 'payroll_run'), pk=pk)
    employee = payslip.employee

    def body(elements, styles):
        _append_payslip_body(elements, styles, payslip, fmt_money, kpi_table)

    return build_pdf_response(
        f'payslip-{employee.employee_id}-{payslip.payroll_run.payroll_month.strftime("%Y%m")}.pdf',
        'Payslip',
        subtitle=f'{employee.get_full_name()} — {payslip.payroll_run.payroll_month.strftime("%B %Y")}',
        build_body=body,
    )


@login_required
def payroll_run_payslips_pdf(request, pk):
    """Bundle PDF of every payslip in a payroll run, for 'Print All'."""
    from reportlab.platypus import PageBreak
    from utils.report_kit import build_pdf_response, fmt_money, kpi_table

    payroll_run = get_object_or_404(PayrollRun, pk=pk)
    payslips = payroll_run.payslips.select_related('employee').order_by('employee__employee_id')

    def body(elements, styles):
        for index, payslip in enumerate(payslips):
            if index > 0:
                elements.append(PageBreak())
            _append_payslip_body(elements, styles, payslip, fmt_money, kpi_table)

    return build_pdf_response(
        f'payslips-{payroll_run.payroll_number}.pdf',
        f'Payslips — {payroll_run.payroll_number}',
        subtitle=f'{payroll_run.payroll_month.strftime("%B %Y")} — {payslips.count()} employee(s)',
        build_body=body,
    )


# ============================================================================
# Attendance Views
# ============================================================================

@login_required
def attendance_list(request):
    """Display attendance records."""
    attendance_qs = Attendance.objects.all().select_related('employee').order_by('-attendance_date')

    # Filter by date
    date_filter = request.GET.get('date')
    if date_filter:
        attendance_qs = attendance_qs.filter(attendance_date=date_filter)

    # Filter by employee
    employee_id = request.GET.get('employee')
    if employee_id:
        attendance_qs = attendance_qs.filter(employee_id=employee_id)

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        attendance_qs = attendance_qs.filter(status=status_filter)

    # Pagination
    paginator = Paginator(attendance_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats — use today's records when no date filter applied, else filtered records
    stat_qs = attendance_qs if date_filter else Attendance.objects.filter(attendance_date=date.today())
    context = {
        'page_obj': page_obj,
        'attendances': page_obj,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'present_count': stat_qs.filter(status='PRESENT').count(),
        'absent_count': stat_qs.filter(status='ABSENT').count(),
        'late_count': stat_qs.filter(status='LATE').count(),
        'on_leave_count': stat_qs.filter(status='ON_LEAVE').count(),
        'holiday_count': stat_qs.filter(status='HOLIDAY').count(),
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
def attendance_bulk_mark(request):
    """Mark attendance for multiple employees."""
    employees = Employee.objects.filter(status='ACTIVE').order_by('employee_id')

    if request.method == 'POST':
        form = BulkAttendanceForm(request.POST)
        if not form.is_valid():
            context = {
                'form': form,
                'employees': employees,
                'title': 'Bulk Mark Attendance',
            }
            return render(request, 'payroll/attendance_bulk.html', context)

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

    form = BulkAttendanceForm(initial={'attendance_date': date.today()})
    context = {
        'form': form,
        'employees': employees,
        'title': 'Bulk Mark Attendance',
    }
    return render(request, 'payroll/attendance_bulk.html', context)


# ============================================================================
# Leave Management Views
# ============================================================================

@login_required
def leave_list(request):
    """Display leave requests."""
    leaves_qs = Leave.objects.all().select_related('employee', 'approved_by').order_by('-start_date')

    status_filter = request.GET.get('status', '')
    leave_type_filter = request.GET.get('leave_type', '')
    month_filter = request.GET.get('month', '')

    if status_filter:
        leaves_qs = leaves_qs.filter(status=status_filter)
    if leave_type_filter:
        leaves_qs = leaves_qs.filter(leave_type=leave_type_filter)
    if month_filter:
        try:
            year, month = month_filter.split('-')
            leaves_qs = leaves_qs.filter(start_date__year=year, start_date__month=month)
        except (ValueError, AttributeError):
            pass

    paginator = Paginator(leaves_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    today = date.today()
    all_leaves = Leave.objects.all()
    context = {
        'leaves': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status_filter': status_filter,
        'leave_type_filter': leave_type_filter,
        'pending_count': all_leaves.filter(status='PENDING').count(),
        'approved_count': all_leaves.filter(status='APPROVED').count(),
        'rejected_count': all_leaves.filter(status='REJECTED').count(),
        'this_month_count': all_leaves.filter(start_date__year=today.year, start_date__month=today.month).count(),
    }

    return render(request, 'payroll/leave_list.html', context)


@login_required
def leave_create(request):
    """Create leave request."""
    # Pre-populate employee from ?employee= query param
    employee_id = request.GET.get('employee') or request.POST.get('employee')
    employee_obj = None
    if employee_id:
        try:
            employee_obj = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            pass

    if request.method == 'POST':
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save()
            messages.success(request, 'Leave request submitted.')
            return redirect('payroll:leave_list')
    else:
        initial = {}
        if employee_obj:
            initial['employee'] = employee_obj
        form = LeaveForm(initial=initial)

    context = {
        'form': form,
        'title': 'Request Leave',
        'employee': employee_obj,
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
    loans_qs = Loan.objects.all().select_related('employee', 'approved_by').order_by('-disbursement_date')

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        loans_qs = loans_qs.filter(status=status_filter)

    # Filter by employee name/ID search
    employee_search = request.GET.get('employee')
    if employee_search:
        loans_qs = loans_qs.filter(
            Q(employee__first_name__icontains=employee_search) |
            Q(employee__last_name__icontains=employee_search) |
            Q(employee__employee_id__icontains=employee_search)
        )

    # Filter by disbursement date from
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            loans_qs = loans_qs.filter(disbursement_date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass

    # Pagination
    paginator = Paginator(loans_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_loans = Loan.objects.all()
    context = {
        'page_obj': page_obj,
        'loans': page_obj,
        'status_filter': status_filter,
        'is_approver': _is_approver(request.user),
        'total_loans': all_loans.aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00'),
        'active_count': all_loans.filter(status__in=['ACTIVE', 'APPROVED']).count(),
        'paid_count': all_loans.filter(status='COMPLETED').count(),
        'total_balance': all_loans.aggregate(total=Sum('balance'))['total'] or Decimal('0.00'),
    }

    return render(request, 'payroll/loan_list.html', context)


@login_required
def loan_create(request):
    """Create loan application."""
    # Pre-populate employee from ?employee= query param (e.g. linked from employee profile)
    employee_id = request.GET.get('employee') or request.POST.get('employee')
    employee_obj = None
    if employee_id:
        try:
            employee_obj = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            pass

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save()
            if _is_approver(request.user):
                # Admins/approvers can process loans and advances immediately —
                # skip the pending-approval queue entirely.
                loan.status = 'APPROVED'
                loan.approved_by = request.user
                loan.approved_at = timezone.now()
                loan.save()
                messages.success(
                    request,
                    f'Loan approved and disbursed to {loan.employee.get_full_name()}. '
                    f'Posted to the expense ledger.'
                )
            else:
                messages.success(request, 'Loan application submitted for approval.')
            return redirect('payroll:loan_list')
    else:
        initial = {}
        if employee_obj:
            initial['employee'] = employee_obj
        form = LoanForm(initial=initial)

    context = {
        'form': form,
        'title': 'Apply for Loan',
        'employee': employee_obj,
        'is_approver': _is_approver(request.user),
    }

    return render(request, 'payroll/loan_form.html', context)


@login_required
@require_http_methods(["POST"])
def loan_approve(request, pk):
    """Approve a loan."""
    loan = get_object_or_404(Loan, pk=pk)

    if not _is_approver(request.user):
        return JsonResponse({
            'error': 'Not authorized',
            'message': 'You are not authorized to approve loans.'
        }, status=403)

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

def _compute_payroll_report_context(request):
    """Filter + aggregate payroll data — shared by the on-screen reports
    view and its PDF/Excel/CSV exports."""
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    payslip_qs = Payslip.objects.select_related('employee', 'payroll_run').all()
    commission_qs = Commission.objects.all()
    deduction_qs = Deduction.objects.all()
    attendance_qs = Attendance.objects.all()
    leave_qs = Leave.objects.filter(status='APPROVED')
    loan_qs = Loan.objects.all()

    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            payslip_qs = payslip_qs.filter(payroll_run__payroll_month__gte=date_from)
            commission_qs = commission_qs.filter(commission_date__gte=date_from)
            attendance_qs = attendance_qs.filter(attendance_date__gte=date_from)
            leave_qs = leave_qs.filter(start_date__gte=date_from)
        except ValueError:
            pass

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            payslip_qs = payslip_qs.filter(payroll_run__payroll_month__lte=date_to)
            commission_qs = commission_qs.filter(commission_date__lte=date_to)
            attendance_qs = attendance_qs.filter(attendance_date__lte=date_to)
            leave_qs = leave_qs.filter(end_date__lte=date_to)
        except ValueError:
            pass

    # Overall payroll totals from payslips
    payslip_totals = payslip_qs.aggregate(
        gross=Sum('gross_salary'),
        deductions=Sum('total_deductions'),
        net=Sum('net_salary'),
    )
    total_payroll = payslip_totals['gross'] or Decimal('0.00')
    total_deductions = payslip_totals['deductions'] or Decimal('0.00')
    net_pay = payslip_totals['net'] or Decimal('0.00')

    # Commission totals
    total_commissions = commission_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_commissions_paid = commission_qs.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    pending_commissions_count = commission_qs.filter(status='PENDING').count()

    # Monthly salary stats from PayrollRun
    monthly_values = list(PayrollRun.objects.values_list('total_net', flat=True).filter(total_net__gt=0))
    if monthly_values:
        avg_monthly_salary = sum(monthly_values) / len(monthly_values)
        highest_month = max(monthly_values)
        lowest_month = min(monthly_values)
    else:
        avg_monthly_salary = highest_month = lowest_month = Decimal('0.00')

    # Top earner by paid commission
    top_earner_row = (
        commission_qs.filter(status='PAID')
        .values('employee__first_name', 'employee__last_name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )
    if top_earner_row:
        top_earner = {
            'name': f"{top_earner_row['employee__first_name']} {top_earner_row['employee__last_name']}",
            'amount': top_earner_row['total'],
        }
    else:
        top_earner = {'name': '—', 'amount': Decimal('0.00')}

    # Deduction breakdown by type
    deduction_by_type = list(
        deduction_qs.values('deduction_type')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total_deduction_sum = sum(d['total'] for d in deduction_by_type if d['total']) or Decimal('1.00')
    deduction_type_labels = dict(Deduction.DEDUCTION_TYPE_CHOICES)
    deduction_summary = [
        {
            'type_display': deduction_type_labels.get(d['deduction_type'], d['deduction_type']),
            'amount': d['total'] or Decimal('0.00'),
            'percentage': min(100, float((d['total'] or 0) / total_deduction_sum * 100)),
        }
        for d in deduction_by_type
    ]

    # Attendance stats
    total_att = attendance_qs.count() or 1
    present_days = attendance_qs.filter(status='PRESENT').count()
    absent_days = attendance_qs.filter(status='ABSENT').count()
    late_days = attendance_qs.filter(status='LATE').count()
    avg_attendance_rate = (present_days + late_days) / total_att * 100

    # Leave utilization (approved leaves only)
    leave_by_type = list(
        leave_qs.values('leave_type')
        .annotate(total_days=Sum('days_requested'))
        .order_by('-total_days')
    )
    total_leave_days = sum(l['total_days'] for l in leave_by_type if l['total_days']) or 1
    leave_type_labels = dict(Leave.LEAVE_TYPE_CHOICES)
    leave_stats = [
        {
            'type_display': leave_type_labels.get(l['leave_type'], l['leave_type']),
            'days': l['total_days'] or 0,
            'percentage': min(100, float((l['total_days'] or 0) / total_leave_days * 100)),
        }
        for l in leave_by_type
    ]

    # Loan portfolio
    loan_totals = loan_qs.aggregate(
        total_amount=Sum('loan_amount'),
        total_balance=Sum('balance'),
    )
    total_loans_amount = loan_totals['total_amount'] or Decimal('0.00')
    outstanding_balance = loan_totals['total_balance'] or Decimal('0.00')
    repaid = total_loans_amount - outstanding_balance
    repayment_rate = float(repaid / (total_loans_amount or Decimal('1.00')) * 100) if total_loans_amount else 0.0

    context = {
        'title': 'Payroll Reports',
        'payslip_qs': payslip_qs,
        'date_from_str': date_from_str or '',
        'date_to_str': date_to_str or '',
        'total_payroll': total_payroll,
        'total_commissions': total_commissions,
        'total_deductions': total_deductions,
        'net_pay': net_pay,
        'avg_monthly_salary': avg_monthly_salary,
        'highest_month': highest_month,
        'lowest_month': lowest_month,
        'total_commissions_paid': total_commissions_paid,
        'pending_commissions_count': pending_commissions_count,
        'top_earner': top_earner,
        'deduction_summary': deduction_summary,
        'avg_attendance_rate': avg_attendance_rate,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'leave_stats': leave_stats,
        'total_loans_amount': total_loans_amount,
        'outstanding_balance': outstanding_balance,
        'repayment_rate': repayment_rate,
    }
    return context


@login_required
def payroll_reports(request):
    context = _compute_payroll_report_context(request)
    return render(request, 'payroll/reports.html', context)


@login_required
def payroll_reports_pdf(request):
    from utils.report_kit import build_pdf_response, styled_table, kpi_table, fmt_money
    ctx = _compute_payroll_report_context(request)

    def body(elements, styles):
        elements.append(kpi_table([
            ('Total Payroll (Gross)', fmt_money(ctx['total_payroll'])),
            ('Total Deductions', fmt_money(ctx['total_deductions'])),
            ('Net Pay', fmt_money(ctx['net_pay'])),
            ('Total Commissions', fmt_money(ctx['total_commissions'])),
            ('Commissions Paid', fmt_money(ctx['total_commissions_paid'])),
            ('Outstanding Loans', fmt_money(ctx['outstanding_balance'])),
        ]))
        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Payslips', styles['ReportSectionHeading']))
        rows = [['Employee', 'Period', 'Gross', 'Deductions', 'Net']]
        for p in ctx['payslip_qs']:
            rows.append([
                f"{p.employee.first_name} {p.employee.last_name}",
                p.payroll_run.payroll_month.strftime('%b %Y'),
                fmt_money(p.gross_salary), fmt_money(p.total_deductions), fmt_money(p.net_salary),
            ])
        elements.append(styled_table(rows, col_widths=[1.8 * inch, 1 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch], align_right_from=2))

    return build_pdf_response('payroll_report.pdf', 'Payroll Report', build_body=body)


@login_required
def payroll_reports_excel(request):
    from utils.report_kit import build_excel_response
    ctx = _compute_payroll_report_context(request)
    headers = ['Employee', 'Period', 'Gross', 'Deductions', 'Net']
    rows = [
        [f"{p.employee.first_name} {p.employee.last_name}", p.payroll_run.payroll_month.strftime('%Y-%m'), float(p.gross_salary), float(p.total_deductions), float(p.net_salary)]
        for p in ctx['payslip_qs']
    ]
    return build_excel_response('payroll_report.xlsx', 'Payslips', headers, rows, currency_cols={3, 4, 5})


@login_required
def payroll_reports_csv(request):
    from utils.report_kit import build_csv_response
    ctx = _compute_payroll_report_context(request)
    headers = ['Employee', 'Period', 'Gross', 'Deductions', 'Net']
    rows = [
        [f"{p.employee.first_name} {p.employee.last_name}", p.payroll_run.payroll_month.strftime('%Y-%m'), p.gross_salary, p.total_deductions, p.net_salary]
        for p in ctx['payslip_qs']
    ]
    return build_csv_response('payroll_report.csv', headers, rows)