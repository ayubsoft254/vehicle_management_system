"""
Utility functions for the expenses app.
Handles calculations, reports, notifications, and expense processing.
"""

from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar
import csv
from io import StringIO


# ============================================================================
# Financial Calculations
# ============================================================================

def calculate_expense_totals(expenses):
    """
    Calculate comprehensive totals for a queryset of expenses.
    """
    totals = expenses.aggregate(
        total_amount=Sum('total_amount'),
        total_tax=Sum('tax_amount'),
        count=Count('id'),
        average=Avg('total_amount')
    )
    
    return {
        'total_amount': totals['total_amount'] or Decimal('0.00'),
        'total_tax': totals['total_tax'] or Decimal('0.00'),
        'count': totals['count'] or 0,
        'average': totals['average'] or Decimal('0.00'),
    }


def calculate_category_breakdown(expenses):
    """
    Break down expenses by category with totals and percentages.
    """
    category_data = expenses.values('category__name').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')
    
    grand_total = expenses.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    breakdown = []
    for item in category_data:
        total = item['total'] or Decimal('0.00')
        percentage = (total / grand_total * 100) if grand_total > 0 else 0
        
        breakdown.append({
            'category': item['category__name'],
            'total': total,
            'count': item['count'],
            'percentage': round(percentage, 2)
        })
    
    return breakdown


def calculate_monthly_trends(expenses, months=12):
    """
    Calculate expense trends over specified number of months.
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30 * months)
    
    from django.db.models.functions import TruncMonth
    
    monthly_data = expenses.filter(
        expense_date__gte=start_date,
        expense_date__lte=end_date
    ).annotate(
        month=TruncMonth('expense_date')
    ).values('month').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('month')
    
    # Fill in missing months with zero values
    result = []
    current_date = start_date.replace(day=1)
    
    monthly_dict = {item['month'].date(): item for item in monthly_data}
    
    while current_date <= end_date:
        month_key = current_date
        
        if month_key in monthly_dict:
            result.append({
                'month': month_key.strftime('%Y-%m'),
                'month_name': month_key.strftime('%B %Y'),
                'total': monthly_dict[month_key]['total'],
                'count': monthly_dict[month_key]['count']
            })
        else:
            result.append({
                'month': month_key.strftime('%Y-%m'),
                'month_name': month_key.strftime('%B %Y'),
                'total': Decimal('0.00'),
                'count': 0
            })
        
        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return result


def calculate_budget_status(category, year=None, month=None):
    """
    Calculate budget status for a category in a given month.
    """
    if not category.budget_limit:
        return None
    
    if not year or not month:
        now = timezone.now()
        year = now.year
        month = now.month
    
    # Get start and end of month
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    # Calculate spent amount
    spent = category.expenses.filter(
        status='APPROVED',
        expense_date__gte=start_date,
        expense_date__lte=end_date
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    remaining = category.budget_limit - spent
    percentage = (spent / category.budget_limit * 100) if category.budget_limit > 0 else 0
    
    return {
        'budget_limit': category.budget_limit,
        'spent': spent,
        'remaining': remaining,
        'percentage': round(percentage, 2),
        'is_over_budget': spent > category.budget_limit,
        'is_near_limit': percentage >= 80,
    }


def calculate_reimbursement_amount(user, status='pending'):
    """
    Calculate total reimbursement amount for a user.
    status: 'pending' (approved but not paid) or 'all'
    """
    from .models import Expense
    
    expenses = Expense.objects.filter(
        submitted_by=user,
        is_reimbursable=True
    )
    
    if status == 'pending':
        expenses = expenses.filter(
            status='APPROVED',
            reimbursed=False
        )
    
    total = expenses.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    count = expenses.count()
    
    return {
        'total': total,
        'count': count,
        'expenses': expenses
    }


# ============================================================================
# Expense Analysis
# ============================================================================

def analyze_spending_patterns(user, days=90):
    """
    Analyze user's spending patterns over specified period.
    """
    from .models import Expense
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    expenses = Expense.objects.filter(
        submitted_by=user,
        status='APPROVED',
        expense_date__gte=start_date,
        expense_date__lte=end_date
    )
    
    # Overall stats
    stats = calculate_expense_totals(expenses)
    
    # By category
    by_category = calculate_category_breakdown(expenses)
    
    # By payment method
    by_payment = expenses.values('payment_method').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Average per day
    daily_average = stats['total_amount'] / days if days > 0 else Decimal('0.00')
    
    # Top expenses
    top_expenses = expenses.order_by('-total_amount')[:5]
    
    return {
        'period': {
            'start': start_date,
            'end': end_date,
            'days': days
        },
        'totals': stats,
        'daily_average': round(daily_average, 2),
        'by_category': by_category,
        'by_payment_method': list(by_payment),
        'top_expenses': top_expenses,
    }


def get_expense_statistics(filters=None):
    """
    Get comprehensive expense statistics with optional filters.
    """
    from .models import Expense
    
    expenses = Expense.objects.all()
    
    if filters:
        if 'date_from' in filters and filters['date_from']:
            expenses = expenses.filter(expense_date__gte=filters['date_from'])
        if 'date_to' in filters and filters['date_to']:
            expenses = expenses.filter(expense_date__lte=filters['date_to'])
        if 'category' in filters and filters['category']:
            expenses = expenses.filter(category=filters['category'])
        if 'status' in filters and filters['status']:
            expenses = expenses.filter(status=filters['status'])
    
    # Status breakdown
    status_breakdown = {}
    from .models import Expense as ExpenseModel
    for status, label in ExpenseModel.STATUS_CHOICES:
        count = expenses.filter(status=status).count()
        amount = expenses.filter(status=status).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or Decimal('0.00')
        status_breakdown[status] = {
            'label': label,
            'count': count,
            'amount': amount
        }
    
    return {
        'total': calculate_expense_totals(expenses),
        'by_status': status_breakdown,
        'by_category': calculate_category_breakdown(expenses),
    }


def identify_unusual_expenses(user, threshold_multiplier=3.0):
    """
    Identify expenses that are unusually high compared to user's average.
    """
    from .models import Expense
    
    # Calculate user's average expense
    avg_expense = Expense.objects.filter(
        submitted_by=user,
        status='APPROVED'
    ).aggregate(Avg('total_amount'))['total_amount__avg'] or Decimal('0.00')
    
    threshold = avg_expense * Decimal(str(threshold_multiplier))
    
    # Find expenses above threshold
    unusual = Expense.objects.filter(
        submitted_by=user,
        total_amount__gt=threshold
    ).order_by('-total_amount')
    
    return {
        'average': avg_expense,
        'threshold': threshold,
        'unusual_expenses': unusual,
        'count': unusual.count()
    }


# ============================================================================
# Report Generation
# ============================================================================

def generate_expense_report_data(report):
    """
    Generate comprehensive data for an expense report.
    """
    expenses = report.items.select_related(
        'expense__category', 'expense__submitted_by'
    ).order_by('expense__expense_date')
    
    # Calculate totals
    totals = {
        'count': expenses.count(),
        'total_amount': Decimal('0.00'),
        'total_tax': Decimal('0.00'),
        'reimbursable': Decimal('0.00'),
    }
    
    # Category breakdown
    category_totals = {}
    
    for item in expenses:
        expense = item.expense
        totals['total_amount'] += expense.total_amount
        totals['total_tax'] += expense.tax_amount
        
        if expense.is_reimbursable:
            totals['reimbursable'] += expense.total_amount
        
        # Category totals
        category_name = expense.category.name if expense.category else 'Uncategorized'
        if category_name not in category_totals:
            category_totals[category_name] = Decimal('0.00')
        category_totals[category_name] += expense.total_amount
    
    return {
        'report': report,
        'expenses': expenses,
        'totals': totals,
        'category_totals': category_totals,
    }


def export_expenses_to_csv(expenses):
    """
    Export expenses to CSV format.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Date', 'Title', 'Category', 'Amount', 'Currency', 'Tax',
        'Total', 'Status', 'Payment Method', 'Vendor', 'Invoice',
        'Submitted By', 'Reimbursable', 'Reimbursed'
    ])
    
    # Data
    for expense in expenses:
        writer.writerow([
            expense.expense_date.strftime('%Y-%m-%d'),
            expense.title,
            expense.category.name if expense.category else '',
            str(expense.amount),
            expense.currency,
            str(expense.tax_amount),
            str(expense.total_amount),
            expense.get_status_display(),
            expense.get_payment_method_display(),
            expense.vendor_name,
            expense.invoice_number,
            expense.submitted_by.username,
            'Yes' if expense.is_reimbursable else 'No',
            'Yes' if expense.reimbursed else 'No',
        ])
    
    return output.getvalue()


def generate_monthly_summary(year, month, user=None):
    """
    Generate monthly expense summary.
    """
    from .models import Expense
    
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    expenses = Expense.objects.filter(
        expense_date__gte=start_date,
        expense_date__lte=end_date,
        status='APPROVED'
    )
    
    if user:
        expenses = expenses.filter(submitted_by=user)
    
    return {
        'period': {
            'year': year,
            'month': month,
            'month_name': start_date.strftime('%B %Y'),
            'start_date': start_date,
            'end_date': end_date,
        },
        'totals': calculate_expense_totals(expenses),
        'by_category': calculate_category_breakdown(expenses),
        'expenses': expenses,
    }


# ============================================================================
# Recurring Expense Processing
# ============================================================================

def get_due_recurring_expenses():
    """
    Get recurring expenses that are due for generation.
    """
    from .models import RecurringExpense
    
    today = timezone.now().date()
    due_expenses = []
    
    active_recurring = RecurringExpense.objects.filter(
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )
    
    for recurring in active_recurring:
        if should_generate_recurring(recurring):
            due_expenses.append(recurring)
    
    return due_expenses


def should_generate_recurring(recurring):
    """
    Check if a recurring expense should generate a new expense.
    """
    if not recurring.is_active:
        return False
    
    today = timezone.now().date()
    
    # Check if within date range
    if today < recurring.start_date:
        return False
    if recurring.end_date and today > recurring.end_date:
        return False
    
    # Check if already generated recently
    if not recurring.last_generated:
        return True
    
    days_since_last = (today - recurring.last_generated).days
    
    if recurring.frequency == 'WEEKLY':
        return days_since_last >= 7
    elif recurring.frequency == 'MONTHLY':
        return days_since_last >= 30
    elif recurring.frequency == 'QUARTERLY':
        return days_since_last >= 90
    elif recurring.frequency == 'YEARLY':
        return days_since_last >= 365
    
    return False


def generate_recurring_expenses(dry_run=False):
    """
    Generate expenses from due recurring templates.
    Returns count of generated expenses.
    """
    due_recurring = get_due_recurring_expenses()
    count = 0
    
    for recurring in due_recurring:
        if not dry_run:
            try:
                recurring.generate_expense()
                count += 1
            except Exception as e:
                print(f"Error generating recurring expense {recurring.id}: {e}")
        else:
            count += 1
    
    return count


# ============================================================================
# Notification Utilities
# ============================================================================

def notify_expense_submitted(expense):
    """
    Send notification when expense is submitted for approval.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get users with approval permission
    approvers = User.objects.filter(
        is_active=True,
        user_permissions__codename='approve_expense'
    ) | User.objects.filter(
        is_active=True,
        groups__permissions__codename='approve_expense'
    )
    
    approvers = approvers.distinct()
    
    for approver in approvers:
        if approver.email:
            subject = f"Expense Approval Required: {expense.title}"
            message = f"""
An expense has been submitted for your approval.

Expense: {expense.title}
Amount: {expense.currency} {expense.total_amount}
Submitted by: {expense.submitted_by.get_full_name() or expense.submitted_by.username}
Date: {expense.expense_date}

Please review and approve/reject this expense in the system.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [approver.email],
                fail_silently=True,
            )


def notify_expense_approved(expense):
    """
    Send notification when expense is approved.
    """
    if expense.submitted_by.email:
        subject = f"Expense Approved: {expense.title}"
        message = f"""
Your expense has been approved.

Expense: {expense.title}
Amount: {expense.currency} {expense.total_amount}
Approved by: {expense.approved_by.get_full_name() or expense.approved_by.username}
Date: {expense.approved_at.strftime('%Y-%m-%d %H:%M')}

{'Your reimbursement will be processed soon.' if expense.is_reimbursable else ''}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [expense.submitted_by.email],
            fail_silently=True,
        )


def notify_expense_rejected(expense):
    """
    Send notification when expense is rejected.
    """
    if expense.submitted_by.email:
        subject = f"Expense Rejected: {expense.title}"
        message = f"""
Your expense has been rejected.

Expense: {expense.title}
Amount: {expense.currency} {expense.total_amount}
Rejected by: {expense.approved_by.get_full_name() or expense.approved_by.username}
Reason: {expense.rejection_reason}

Please review and resubmit if necessary.
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [expense.submitted_by.email],
            fail_silently=True,
        )


def notify_budget_threshold(category, percentage=80):
    """
    Send notification when category budget reaches threshold.
    """
    budget_status = calculate_budget_status(category)
    
    if budget_status and budget_status['percentage'] >= percentage:
        # Notify admin users
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admins = User.objects.filter(is_staff=True, is_active=True)
        
        for admin in admins:
            if admin.email:
                subject = f"Budget Alert: {category.name}"
                message = f"""
Budget threshold alert for category: {category.name}

Budget Limit: {category.budget_limit}
Spent: {budget_status['spent']} ({budget_status['percentage']}%)
Remaining: {budget_status['remaining']}

Please review expenses in this category.
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin.email],
                    fail_silently=True,
                )


# ============================================================================
# Validation Utilities
# ============================================================================

def validate_expense_date(expense_date):
    """
    Validate expense date is reasonable.
    """
    today = date.today()
    
    # Can't be in the future
    if expense_date > today:
        return False, "Expense date cannot be in the future."
    
    # Can't be too old (e.g., 1 year)
    one_year_ago = today - timedelta(days=365)
    if expense_date < one_year_ago:
        return False, "Expense date cannot be more than 1 year old."
    
    return True, ""


def validate_expense_amount(amount, category=None):
    """
    Validate expense amount against limits.
    """
    if amount <= 0:
        return False, "Amount must be greater than zero."
    
    # Check against category budget if provided
    if category and category.budget_limit:
        month_total = category.get_total_expenses(
            start_date=date.today().replace(day=1),
            end_date=date.today()
        )
        
        if (month_total + amount) > category.budget_limit:
            return False, f"This expense would exceed the category budget limit of {category.budget_limit}."
    
    return True, ""


def check_duplicate_expense(user, title, amount, expense_date):
    """
    Check for potential duplicate expenses.
    """
    from .models import Expense
    
    # Look for expenses with same title, amount, and date within 7 days
    date_from = expense_date - timedelta(days=7)
    date_to = expense_date + timedelta(days=7)
    
    duplicates = Expense.objects.filter(
        submitted_by=user,
        title__iexact=title,
        amount=amount,
        expense_date__gte=date_from,
        expense_date__lte=date_to
    )
    
    return duplicates.exists(), duplicates


# ============================================================================
# Dashboard Utilities
# ============================================================================

def get_dashboard_stats(user):
    """
    Get statistics for expense dashboard.
    """
    from .models import Expense
    
    # User's expenses
    expenses = Expense.objects.filter(submitted_by=user)
    
    # Count by status
    status_counts = {}
    for status, label in Expense.STATUS_CHOICES:
        status_counts[status] = expenses.filter(status=status).count()
    
    # Pending reimbursement
    pending_reimbursement = calculate_reimbursement_amount(user, status='pending')
    
    # This month's expenses
    now = timezone.now()
    month_start = now.replace(day=1).date()
    month_expenses = expenses.filter(
        expense_date__gte=month_start,
        status='APPROVED'
    )
    month_total = month_expenses.aggregate(
        Sum('total_amount')
    )['total_amount__sum'] or Decimal('0.00')
    
    return {
        'total_expenses': expenses.count(),
        'status_counts': status_counts,
        'pending_reimbursement': pending_reimbursement,
        'this_month_total': month_total,
        'this_month_count': month_expenses.count(),
    }