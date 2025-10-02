"""
Utility functions for the payroll app.
Handles salary calculations, tax computation, reporting, and payroll processing.
"""

from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar
from io import BytesIO


# ============================================================================
# Salary Calculations
# ============================================================================

def calculate_gross_salary(salary_structure):
    """
    Calculate total gross salary including all allowances.
    """
    return (
        salary_structure.basic_salary +
        salary_structure.housing_allowance +
        salary_structure.transport_allowance +
        salary_structure.medical_allowance +
        salary_structure.meal_allowance +
        salary_structure.other_allowances
    )


def calculate_prorated_salary(gross_salary, days_worked, working_days):
    """
    Calculate prorated salary based on days worked.
    """
    if working_days == 0:
        return Decimal('0.00')
    
    daily_rate = gross_salary / Decimal(str(working_days))
    return daily_rate * Decimal(str(days_worked))


def calculate_overtime_pay(hourly_rate, hours_worked, overtime_multiplier=1.5):
    """
    Calculate overtime payment.
    """
    overtime_rate = hourly_rate * Decimal(str(overtime_multiplier))
    return overtime_rate * Decimal(str(hours_worked))


# ============================================================================
# Tax Calculations (Kenya PAYE)
# ============================================================================

def calculate_paye_tax(gross_salary):
    """
    Calculate Kenya PAYE (Pay As You Earn) tax.
    Tax bands as of 2024 (simplified):
    - Up to 24,000: 10%
    - 24,001 to 32,333: 25%
    - 32,334 to 500,000: 30%
    - 500,001 to 800,000: 32.5%
    - Above 800,000: 35%
    """
    monthly_gross = gross_salary
    tax = Decimal('0.00')
    
    # Tax bands
    bands = [
        (Decimal('24000'), Decimal('0.10')),
        (Decimal('8333'), Decimal('0.25')),   # 32,333 - 24,000
        (Decimal('467667'), Decimal('0.30')), # 500,000 - 32,333
        (Decimal('300000'), Decimal('0.325')), # 800,000 - 500,000
    ]
    
    remaining = monthly_gross
    
    for band_limit, rate in bands:
        if remaining <= 0:
            break
        
        taxable_in_band = min(remaining, band_limit)
        tax += taxable_in_band * rate
        remaining -= taxable_in_band
    
    # Anything above 800,000
    if remaining > 0:
        tax += remaining * Decimal('0.35')
    
    # Personal relief (2,400 per month in Kenya)
    personal_relief = Decimal('2400')
    tax = max(tax - personal_relief, Decimal('0.00'))
    
    return tax


def calculate_nhif_contribution(gross_salary):
    """
    Calculate NHIF (National Hospital Insurance Fund) contribution.
    Based on Kenya NHIF rates 2024.
    """
    monthly_gross = gross_salary
    
    # NHIF contribution bands
    if monthly_gross <= 5999:
        return Decimal('150')
    elif monthly_gross <= 7999:
        return Decimal('300')
    elif monthly_gross <= 11999:
        return Decimal('400')
    elif monthly_gross <= 14999:
        return Decimal('500')
    elif monthly_gross <= 19999:
        return Decimal('600')
    elif monthly_gross <= 24999:
        return Decimal('750')
    elif monthly_gross <= 29999:
        return Decimal('850')
    elif monthly_gross <= 34999:
        return Decimal('900')
    elif monthly_gross <= 39999:
        return Decimal('950')
    elif monthly_gross <= 44999:
        return Decimal('1000')
    elif monthly_gross <= 49999:
        return Decimal('1100')
    elif monthly_gross <= 59999:
        return Decimal('1200')
    elif monthly_gross <= 69999:
        return Decimal('1300')
    elif monthly_gross <= 79999:
        return Decimal('1400')
    elif monthly_gross <= 89999:
        return Decimal('1500')
    elif monthly_gross <= 99999:
        return Decimal('1600')
    else:
        return Decimal('1700')


def calculate_nssf_contribution(gross_salary):
    """
    Calculate NSSF (National Social Security Fund) contribution.
    Both employee and employer contribute.
    """
    # NSSF Tier I (Lower Earnings Limit): Up to KES 7,000
    # NSSF Tier II (Upper Earnings Limit): KES 7,001 to KES 36,000
    
    tier1_limit = Decimal('7000')
    tier2_limit = Decimal('36000')
    rate = Decimal('0.06')  # 6%
    
    contribution = Decimal('0.00')
    
    # Tier I contribution
    tier1_amount = min(gross_salary, tier1_limit)
    contribution += tier1_amount * rate
    
    # Tier II contribution (if applicable)
    if gross_salary > tier1_limit:
        tier2_amount = min(gross_salary - tier1_limit, tier2_limit - tier1_limit)
        contribution += tier2_amount * rate
    
    return contribution


def calculate_housing_levy(gross_salary):
    """
    Calculate Affordable Housing Levy (1.5% of gross salary).
    Introduced in Kenya 2023.
    """
    rate = Decimal('0.015')  # 1.5%
    return gross_salary * rate


def calculate_net_salary(gross_salary, deductions):
    """
    Calculate net salary after all deductions.
    """
    total_deductions = sum(deductions.values())
    return gross_salary - total_deductions


# ============================================================================
# Payroll Processing
# ============================================================================

def get_working_days(year, month):
    """
    Calculate working days in a month (excluding weekends).
    """
    _, last_day = calendar.monthrange(year, month)
    working_days = 0
    
    for day in range(1, last_day + 1):
        weekday = date(year, month, day).weekday()
        # 0-4 are Monday to Friday
        if weekday < 5:
            working_days += 1
    
    return working_days


def get_employee_attendance_summary(employee, year, month):
    """
    Get attendance summary for an employee for a given month.
    """
    from .models import Attendance
    
    attendance_records = Attendance.objects.filter(
        employee=employee,
        attendance_date__year=year,
        attendance_date__month=month
    )
    
    summary = {
        'total_days': calendar.monthrange(year, month)[1],
        'working_days': get_working_days(year, month),
        'present': attendance_records.filter(status='PRESENT').count(),
        'absent': attendance_records.filter(status='ABSENT').count(),
        'late': attendance_records.filter(status='LATE').count(),
        'half_day': attendance_records.filter(status='HALF_DAY').count(),
        'on_leave': attendance_records.filter(status='ON_LEAVE').count(),
        'holiday': attendance_records.filter(status='HOLIDAY').count(),
    }
    
    # Calculate total hours worked
    total_hours = attendance_records.aggregate(
        Sum('hours_worked')
    )['hours_worked__sum'] or Decimal('0.00')
    
    summary['total_hours'] = total_hours
    
    return summary


def calculate_employee_payslip(employee, payroll_month):
    """
    Calculate complete payslip for an employee.
    """
    from .models import Commission, Deduction
    
    year = payroll_month.year
    month = payroll_month.month
    
    # Get salary structure
    if not hasattr(employee, 'salary_structure'):
        return None
    
    salary = employee.salary_structure
    
    # Basic calculations
    gross_salary = calculate_gross_salary(salary)
    
    # Get attendance
    attendance = get_employee_attendance_summary(employee, year, month)
    
    # Prorate salary if absent
    if attendance['absent'] > 0:
        prorated_basic = calculate_prorated_salary(
            salary.basic_salary,
            attendance['present'],
            attendance['working_days']
        )
    else:
        prorated_basic = salary.basic_salary
    
    # Get commissions for the month
    commissions = Commission.objects.filter(
        employee=employee,
        payroll_month=payroll_month,
        status='APPROVED'
    )
    commission_total = commissions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Calculate deductions
    deductions = employee.deductions.filter(is_active=True)
    
    deduction_breakdown = {
        'income_tax': Decimal('0.00'),
        'nhif': Decimal('0.00'),
        'nssf': Decimal('0.00'),
        'housing_levy': Decimal('0.00'),
        'pension': Decimal('0.00'),
        'insurance': Decimal('0.00'),
        'loan': Decimal('0.00'),
        'other': Decimal('0.00'),
    }
    
    # Calculate statutory deductions
    deduction_breakdown['income_tax'] = calculate_paye_tax(gross_salary)
    deduction_breakdown['nhif'] = calculate_nhif_contribution(gross_salary)
    deduction_breakdown['nssf'] = calculate_nssf_contribution(gross_salary)
    deduction_breakdown['housing_levy'] = calculate_housing_levy(gross_salary)
    
    # Apply custom deductions
    for deduction in deductions:
        if deduction.is_applicable_for_month(year, month):
            amount = deduction.calculate_deduction_amount(gross_salary)
            
            if deduction.deduction_type == 'PENSION':
                deduction_breakdown['pension'] += amount
            elif deduction.deduction_type == 'INSURANCE':
                deduction_breakdown['insurance'] += amount
            elif deduction.deduction_type in ['LOAN', 'ADVANCE']:
                deduction_breakdown['loan'] += amount
            else:
                deduction_breakdown['other'] += amount
    
    # Calculate totals
    total_earnings = (
        prorated_basic +
        salary.housing_allowance +
        salary.transport_allowance +
        salary.medical_allowance +
        salary.meal_allowance +
        salary.other_allowances +
        commission_total
    )
    
    total_deductions = sum(deduction_breakdown.values())
    net_salary = total_earnings - total_deductions
    
    return {
        'basic_salary': prorated_basic,
        'housing_allowance': salary.housing_allowance,
        'transport_allowance': salary.transport_allowance,
        'medical_allowance': salary.medical_allowance,
        'meal_allowance': salary.meal_allowance,
        'other_allowances': salary.other_allowances,
        'commission_amount': commission_total,
        'gross_salary': total_earnings,
        'deductions': deduction_breakdown,
        'total_deductions': total_deductions,
        'net_salary': net_salary,
        'attendance': attendance,
    }


# ============================================================================
# Reporting Functions
# ============================================================================

def generate_payroll_summary(payroll_run):
    """
    Generate summary statistics for a payroll run.
    """
    payslips = payroll_run.payslips.all()
    
    summary = {
        'total_employees': payslips.count(),
        'total_gross': payslips.aggregate(Sum('gross_salary'))['gross_salary__sum'] or Decimal('0.00'),
        'total_deductions': payslips.aggregate(Sum('total_deductions'))['total_deductions__sum'] or Decimal('0.00'),
        'total_net': payslips.aggregate(Sum('net_salary'))['net_salary__sum'] or Decimal('0.00'),
        'average_gross': payslips.aggregate(Avg('gross_salary'))['gross_salary__avg'] or Decimal('0.00'),
        'average_net': payslips.aggregate(Avg('net_salary'))['net_salary__avg'] or Decimal('0.00'),
    }
    
    # Department breakdown
    dept_breakdown = payslips.values('employee__department').annotate(
        count=Count('id'),
        total_gross=Sum('gross_salary'),
        total_net=Sum('net_salary')
    ).order_by('employee__department')
    
    summary['by_department'] = list(dept_breakdown)
    
    # Tax breakdown
    summary['total_paye'] = payslips.aggregate(Sum('income_tax'))['income_tax__sum'] or Decimal('0.00')
    summary['total_nhif'] = payslips.aggregate(Sum('insurance_deduction'))['insurance_deduction__sum'] or Decimal('0.00')
    summary['total_nssf'] = payslips.aggregate(Sum('pension_contribution'))['pension_contribution__sum'] or Decimal('0.00')
    
    return summary


def generate_employee_payroll_history(employee, months=12):
    """
    Generate payroll history for an employee.
    """
    from .models import Payslip
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30 * months)
    
    payslips = Payslip.objects.filter(
        employee=employee,
        payroll_run__payroll_month__gte=start_date
    ).select_related('payroll_run').order_by('-payroll_run__payroll_month')
    
    history = []
    for payslip in payslips:
        history.append({
            'month': payslip.payroll_run.payroll_month,
            'gross_salary': payslip.gross_salary,
            'total_deductions': payslip.total_deductions,
            'net_salary': payslip.net_salary,
            'commission': payslip.commission_amount,
            'is_paid': payslip.is_paid,
        })
    
    return history


def calculate_annual_earnings(employee, year):
    """
    Calculate total annual earnings for an employee.
    """
    from .models import Payslip
    
    payslips = Payslip.objects.filter(
        employee=employee,
        payroll_run__payroll_month__year=year
    )
    
    totals = payslips.aggregate(
        gross=Sum('gross_salary'),
        deductions=Sum('total_deductions'),
        net=Sum('net_salary'),
        tax=Sum('income_tax'),
    )
    
    return {
        'year': year,
        'total_gross': totals['gross'] or Decimal('0.00'),
        'total_deductions': totals['deductions'] or Decimal('0.00'),
        'total_net': totals['net'] or Decimal('0.00'),
        'total_tax': totals['tax'] or Decimal('0.00'),
        'months_paid': payslips.count(),
    }


def export_payroll_to_csv(payroll_run):
    """
    Export payroll run to CSV format.
    """
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Employee ID', 'Name', 'Department', 'Basic Salary',
        'Allowances', 'Commission', 'Gross Salary', 'PAYE Tax',
        'NHIF', 'NSSF', 'Other Deductions', 'Total Deductions',
        'Net Salary', 'Bank Account'
    ])
    
    # Data
    for payslip in payroll_run.payslips.select_related('employee'):
        employee = payslip.employee
        allowances = (
            payslip.housing_allowance +
            payslip.transport_allowance +
            payslip.medical_allowance +
            payslip.meal_allowance +
            payslip.other_allowances
        )
        
        writer.writerow([
            employee.employee_id,
            employee.get_full_name(),
            employee.department,
            payslip.basic_salary,
            allowances,
            payslip.commission_amount,
            payslip.gross_salary,
            payslip.income_tax,
            payslip.insurance_deduction,
            payslip.pension_contribution,
            payslip.other_deductions,
            payslip.total_deductions,
            payslip.net_salary,
            employee.bank_account_number,
        ])
    
    return output.getvalue()


# ============================================================================
# Leave Management
# ============================================================================

def calculate_leave_balance(employee, year=None):
    """
    Calculate leave balance for an employee.
    """
    from .models import Leave
    
    if not year:
        year = date.today().year
    
    # Annual leave entitlement (21 days per year in Kenya)
    annual_entitlement = 21
    
    # Calculate accrued leave based on tenure
    tenure_years = employee.get_tenure_years()
    if tenure_years < 1:
        # Prorate for first year
        months_worked = (date.today() - employee.hire_date).days / 30
        accrued_leave = (annual_entitlement / 12) * months_worked
    else:
        accrued_leave = annual_entitlement
    
    # Get approved leaves taken this year
    leaves_taken = Leave.objects.filter(
        employee=employee,
        status='APPROVED',
        start_date__year=year
    ).aggregate(Sum('days_requested'))['days_requested__sum'] or 0
    
    # Calculate balance
    balance = accrued_leave - leaves_taken
    
    return {
        'annual_entitlement': annual_entitlement,
        'accrued': round(accrued_leave, 2),
        'taken': leaves_taken,
        'balance': round(balance, 2),
    }


def check_leave_eligibility(employee, leave_type, days_requested):
    """
    Check if employee is eligible for requested leave.
    """
    balance = calculate_leave_balance(employee)
    
    if leave_type == 'ANNUAL':
        if days_requested > balance['balance']:
            return False, f"Insufficient leave balance. Available: {balance['balance']} days"
    
    # Sick leave (typically unlimited but may need documentation)
    elif leave_type == 'SICK':
        if days_requested > 14:
            return True, "Medical certificate required for sick leave exceeding 14 days"
    
    # Maternity leave (3 months in Kenya)
    elif leave_type == 'MATERNITY':
        if days_requested > 90:
            return False, "Maternity leave cannot exceed 90 days"
    
    # Paternity leave (2 weeks in Kenya)
    elif leave_type == 'PATERNITY':
        if days_requested > 14:
            return False, "Paternity leave cannot exceed 14 days"
    
    return True, "Leave request is valid"


# ============================================================================
# Loan Management
# ============================================================================

def calculate_loan_schedule(loan_amount, interest_rate, monthly_payment):
    """
    Calculate loan repayment schedule.
    """
    total_with_interest = loan_amount * (1 + (interest_rate / 100))
    months = int(total_with_interest / monthly_payment) + 1
    
    schedule = []
    balance = total_with_interest
    
    for month in range(1, months + 1):
        payment = min(monthly_payment, balance)
        balance -= payment
        
        schedule.append({
            'month': month,
            'payment': payment,
            'balance': balance,
        })
        
        if balance <= 0:
            break
    
    return schedule


def check_loan_eligibility(employee, loan_amount):
    """
    Check if employee is eligible for a loan.
    """
    from .models import Loan
    
    # Check active loans
    active_loans = Loan.objects.filter(
        employee=employee,
        status__in=['APPROVED', 'ACTIVE']
    )
    
    if active_loans.exists():
        return False, "Employee has an active loan"
    
    # Check salary structure
    if not hasattr(employee, 'salary_structure'):
        return False, "No salary structure defined for employee"
    
    gross_salary = calculate_gross_salary(employee.salary_structure)
    
    # Maximum loan: 3x gross salary
    max_loan = gross_salary * 3
    
    if loan_amount > max_loan:
        return False, f"Loan amount exceeds maximum allowed: {max_loan}"
    
    # Check employment tenure (at least 6 months)
    if employee.get_tenure_years() < 0.5:
        return False, "Employee must have at least 6 months of service"
    
    return True, "Employee is eligible for loan"


# ============================================================================
# Notification Utilities
# ============================================================================

def notify_payslip_ready(payslip):
    """
    Send notification when payslip is ready.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    employee = payslip.employee
    
    if employee.email:
        subject = f"Payslip Ready - {payslip.payroll_run.payroll_month.strftime('%B %Y')}"
        message = f"""
Dear {employee.get_full_name()},

Your payslip for {payslip.payroll_run.payroll_month.strftime('%B %Y')} is now available.

Gross Salary: KES {payslip.gross_salary:,.2f}
Total Deductions: KES {payslip.total_deductions:,.2f}
Net Salary: KES {payslip.net_salary:,.2f}

Please log in to the system to view your detailed payslip.

Best regards,
HR Department
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [employee.email],
            fail_silently=True,
        )


def notify_leave_decision(leave_request):
    """
    Send notification about leave decision.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    employee = leave_request.employee
    
    if employee.email:
        if leave_request.status == 'APPROVED':
            subject = "Leave Request Approved"
            message = f"""
Dear {employee.get_full_name()},

Your leave request has been approved.

Leave Type: {leave_request.get_leave_type_display()}
Start Date: {leave_request.start_date}
End Date: {leave_request.end_date}
Days: {leave_request.days_requested}

Enjoy your time off!

Best regards,
HR Department
            """
        else:
            subject = "Leave Request Status Update"
            message = f"""
Dear {employee.get_full_name()},

Your leave request has been {leave_request.status.lower()}.

Leave Type: {leave_request.get_leave_type_display()}
Start Date: {leave_request.start_date}
End Date: {leave_request.end_date}

{f'Reason: {leave_request.rejection_reason}' if leave_request.rejection_reason else ''}

Please contact HR for more information.

Best regards,
HR Department
            """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [employee.email],
            fail_silently=True,
        )


# ============================================================================
# Dashboard Statistics
# ============================================================================

def get_payroll_dashboard_stats():
    """
    Get statistics for payroll dashboard.
    """
    from .models import Employee, PayrollRun, Leave, Loan, Commission
    
    stats = {
        'active_employees': Employee.objects.filter(status='ACTIVE').count(),
        'total_employees': Employee.objects.count(),
        'pending_leaves': Leave.objects.filter(status='PENDING').count(),
        'pending_loans': Loan.objects.filter(status='PENDING').count(),
        'pending_commissions': Commission.objects.filter(status='PENDING').count(),
    }
    
    # Current month payroll
    today = date.today()
    current_month = today.replace(day=1)
    
    try:
        current_payroll = PayrollRun.objects.get(payroll_month=current_month)
        stats['current_payroll'] = {
            'status': current_payroll.status,
            'total_net': current_payroll.total_net,
            'employees': current_payroll.total_employees,
        }
    except PayrollRun.DoesNotExist:
        stats['current_payroll'] = None
    
    return stats