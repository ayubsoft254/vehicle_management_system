"""
Views for the expenses app.
Handles expense management, approvals, reports, and analytics.
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
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Expense, ExpenseCategory, ExpenseReceipt, ExpenseReport,
    ExpenseTag, RecurringExpense, ExpenseApprovalWorkflow
)
from .forms import (
    ExpenseForm, ExpenseReceiptForm, ExpenseApprovalForm,
    ExpenseCategoryForm, ExpenseReportForm, RecurringExpenseForm,
    ExpenseSearchForm, BulkExpenseActionForm
)


# ============================================================================
# Expense List and Search Views
# ============================================================================

@login_required
def expense_list(request):
    """Display list of expenses with search and filters."""
    form = ExpenseSearchForm(request.GET or None)
    
    # Base queryset - expenses user can view
    if request.user.has_perm('expenses.view_all_expenses'):
        expenses = Expense.objects.all()
    else:
        expenses = Expense.objects.filter(submitted_by=request.user)
    
    expenses = expenses.select_related(
        'submitted_by', 'category', 'approved_by', 'related_vehicle', 'related_client'
    ).prefetch_related('tags')
    
    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        if query:
            expenses = expenses.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(vendor_name__icontains=query) |
                Q(invoice_number__icontains=query)
            )
        
        category = form.cleaned_data.get('category')
        if category:
            expenses = expenses.filter(category=category)
        
        status = form.cleaned_data.get('status')
        if status:
            expenses = expenses.filter(status=status)
        
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            expenses = expenses.filter(expense_date__gte=date_from)
        
        date_to = form.cleaned_data.get('date_to')
        if date_to:
            expenses = expenses.filter(expense_date__lte=date_to)
        
        min_amount = form.cleaned_data.get('min_amount')
        if min_amount:
            expenses = expenses.filter(amount__gte=min_amount)
        
        max_amount = form.cleaned_data.get('max_amount')
        if max_amount:
            expenses = expenses.filter(amount__lte=max_amount)
        
        submitted_by = form.cleaned_data.get('submitted_by')
        if submitted_by:
            expenses = expenses.filter(submitted_by=submitted_by)
        
        is_reimbursable = form.cleaned_data.get('is_reimbursable')
        if is_reimbursable is not None:
            expenses = expenses.filter(is_reimbursable=is_reimbursable)
    
    # Sort expenses
    sort_by = request.GET.get('sort', '-expense_date')
    expenses = expenses.order_by(sort_by)
    
    # Calculate totals for filtered expenses
    totals = expenses.aggregate(
        total_amount=Sum('total_amount'),
        count=Count('id')
    )
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for sidebar
    categories = ExpenseCategory.objects.filter(is_active=True).annotate(
        expense_count=Count('expenses')
    )
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'categories': categories,
        'totals': totals,
        'sort_by': sort_by,
    }
    
    return render(request, 'expenses/expense_list.html', context)


@login_required
def my_expenses(request):
    """Display expenses submitted by current user."""
    expenses = Expense.objects.filter(
        submitted_by=request.user
    ).select_related(
        'category', 'approved_by'
    ).order_by('-expense_date')
    
    # Status counts
    status_counts = {
        'draft': expenses.filter(status='DRAFT').count(),
        'submitted': expenses.filter(status='SUBMITTED').count(),
        'approved': expenses.filter(status='APPROVED').count(),
        'rejected': expenses.filter(status='REJECTED').count(),
        'paid': expenses.filter(status='PAID').count(),
    }
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_counts': status_counts,
    }
    
    return render(request, 'expenses/my_expenses.html', context)


@login_required
def pending_approval(request):
    """Display expenses pending approval."""
    # Only for users with approval permission
    if not request.user.has_perm('expenses.approve_expense'):
        messages.error(request, 'You do not have permission to approve expenses.')
        return redirect('expenses:expense_list')
    
    expenses = Expense.objects.filter(
        status='SUBMITTED'
    ).select_related(
        'submitted_by', 'category'
    ).order_by('expense_date')
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'expenses/pending_approval.html', context)


# ============================================================================
# Expense CRUD Views
# ============================================================================

@login_required
def expense_detail(request, pk):
    """Display expense details."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if not (expense.submitted_by == request.user or 
            request.user.has_perm('expenses.view_all_expenses')):
        messages.error(request, 'You do not have permission to view this expense.')
        return redirect('expenses:expense_list')
    
    # Get receipts
    receipts = expense.receipts.select_related('uploaded_by').order_by('-uploaded_at')
    
    # Get approval workflow
    approvals = expense.approval_workflow.select_related('approver').order_by('level')
    
    # Can user edit/delete?
    can_edit = expense.can_edit(request.user)
    can_delete = expense.can_delete(request.user)
    can_approve = (request.user.has_perm('expenses.approve_expense') and 
                   expense.status == 'SUBMITTED')
    
    context = {
        'expense': expense,
        'receipts': receipts,
        'approvals': approvals,
        'can_edit': can_edit,
        'can_delete': can_delete,
        'can_approve': can_approve,
    }
    
    return render(request, 'expenses/expense_detail.html', context)


@login_required
def expense_create(request):
    """Create a new expense."""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save()
            messages.success(request, f'Expense "{expense.title}" created successfully.')
            
            # Redirect to upload receipt if category requires it
            if expense.category.requires_receipt:
                messages.info(request, 'Please upload a receipt for this expense.')
                return redirect('expenses:receipt_upload', expense_pk=expense.pk)
            
            return redirect('expenses:expense_detail', pk=expense.pk)
    else:
        form = ExpenseForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Expense',
    }
    
    return render(request, 'expenses/expense_form.html', context)


@login_required
def expense_update(request, pk):
    """Update an expense."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if not expense.can_edit(request.user):
        messages.error(request, 'You cannot edit this expense.')
        return redirect('expenses:expense_detail', pk=expense.pk)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            expense = form.save()
            messages.success(request, f'Expense "{expense.title}" updated successfully.')
            return redirect('expenses:expense_detail', pk=expense.pk)
    else:
        form = ExpenseForm(instance=expense, user=request.user)
    
    context = {
        'form': form,
        'expense': expense,
        'title': 'Edit Expense',
    }
    
    return render(request, 'expenses/expense_form.html', context)


@login_required
def expense_delete(request, pk):
    """Delete an expense."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if not expense.can_delete(request.user):
        messages.error(request, 'You cannot delete this expense.')
        return redirect('expenses:expense_detail', pk=expense.pk)
    
    if request.method == 'POST':
        title = expense.title
        expense.delete()
        messages.success(request, f'Expense "{title}" deleted successfully.')
        return redirect('expenses:expense_list')
    
    context = {
        'expense': expense,
    }
    
    return render(request, 'expenses/expense_confirm_delete.html', context)


@login_required
@require_http_methods(["POST"])
def expense_submit(request, pk):
    """Submit expense for approval."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if expense.submitted_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if receipts required
    if expense.category.requires_receipt and not expense.receipts.exists():
        return JsonResponse({
            'error': 'Receipt required',
            'message': 'Please upload a receipt before submitting.'
        }, status=400)
    
    if expense.submit_for_approval():
        messages.success(request, f'Expense "{expense.title}" submitted for approval.')
        return JsonResponse({
            'success': True,
            'message': 'Expense submitted successfully.',
            'status': expense.status
        })
    
    return JsonResponse({
        'error': 'Cannot submit expense',
        'message': f'Expense is currently {expense.get_status_display()}'
    }, status=400)


# ============================================================================
# Expense Approval Views
# ============================================================================

@login_required
def expense_approve(request, pk):
    """Approve or reject an expense."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if not request.user.has_perm('expenses.approve_expense'):
        messages.error(request, 'You do not have permission to approve expenses.')
        return redirect('expenses:expense_detail', pk=expense.pk)
    
    if expense.status != 'SUBMITTED':
        messages.error(request, f'Cannot approve expense with status: {expense.get_status_display()}')
        return redirect('expenses:expense_detail', pk=expense.pk)
    
    if request.method == 'POST':
        form = ExpenseApprovalForm(request.POST, expense=expense)
        if form.is_valid():
            action = form.cleaned_data['action']
            comments = form.cleaned_data.get('comments', '')
            
            if action == 'approve':
                expense.approve(request.user)
                messages.success(request, f'Expense "{expense.title}" approved.')
            else:
                expense.reject(request.user, comments)
                messages.success(request, f'Expense "{expense.title}" rejected.')
            
            return redirect('expenses:expense_detail', pk=expense.pk)
    else:
        form = ExpenseApprovalForm(expense=expense)
    
    context = {
        'form': form,
        'expense': expense,
    }
    
    return render(request, 'expenses/expense_approve.html', context)


@login_required
@require_http_methods(["POST"])
def expense_mark_paid(request, pk):
    """Mark expense as paid."""
    expense = get_object_or_404(Expense, pk=pk)
    
    # Check permission
    if not request.user.has_perm('expenses.mark_paid'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if expense.mark_as_paid():
        messages.success(request, f'Expense "{expense.title}" marked as paid.')
        return JsonResponse({
            'success': True,
            'message': 'Expense marked as paid.',
            'status': expense.status
        })
    
    return JsonResponse({
        'error': 'Cannot mark as paid',
        'message': f'Expense must be approved first'
    }, status=400)


# ============================================================================
# Receipt Management Views
# ============================================================================

@login_required
def receipt_upload(request, expense_pk):
    """Upload receipt for an expense."""
    expense = get_object_or_404(Expense, pk=expense_pk)
    
    # Check permission
    if expense.submitted_by != request.user:
        messages.error(request, 'You can only upload receipts for your own expenses.')
        return redirect('expenses:expense_detail', pk=expense.pk)
    
    if request.method == 'POST':
        form = ExpenseReceiptForm(request.POST, request.FILES, expense=expense, user=request.user)
        if form.is_valid():
            receipt = form.save()
            messages.success(request, 'Receipt uploaded successfully.')
            return redirect('expenses:expense_detail', pk=expense.pk)
    else:
        form = ExpenseReceiptForm(expense=expense, user=request.user)
    
    # Get existing receipts
    receipts = expense.receipts.order_by('-uploaded_at')
    
    context = {
        'form': form,
        'expense': expense,
        'receipts': receipts,
    }
    
    return render(request, 'expenses/receipt_upload.html', context)


@login_required
@require_http_methods(["POST"])
def receipt_delete(request, pk):
    """Delete a receipt."""
    receipt = get_object_or_404(ExpenseReceipt, pk=pk)
    expense = receipt.expense
    
    # Check permission
    if expense.submitted_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Can't delete if expense is submitted/approved
    if expense.status not in ['DRAFT', 'REJECTED']:
        return JsonResponse({
            'error': 'Cannot delete receipt',
            'message': f'Cannot delete receipt for {expense.get_status_display()} expense'
        }, status=400)
    
    receipt.delete()
    messages.success(request, 'Receipt deleted successfully.')
    
    return JsonResponse({
        'success': True,
        'message': 'Receipt deleted successfully.'
    })


# ============================================================================
# Category Management Views
# ============================================================================

@login_required
def category_list(request):
    """Display list of expense categories."""
    categories = ExpenseCategory.objects.filter(
        is_active=True
    ).annotate(
        expense_count=Count('expenses'),
        total_amount=Sum('expenses__total_amount')
    ).order_by('name')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'expenses/category_list.html', context)


@login_required
def category_expenses(request, pk):
    """Display expenses in a specific category."""
    category = get_object_or_404(ExpenseCategory, pk=pk)
    
    # Get expenses for this category
    if request.user.has_perm('expenses.view_all_expenses'):
        expenses = category.expenses.all()
    else:
        expenses = category.expenses.filter(submitted_by=request.user)
    
    expenses = expenses.select_related('submitted_by').order_by('-expense_date')
    
    # Calculate totals
    totals = expenses.aggregate(
        total_amount=Sum('total_amount'),
        count=Count('id')
    )
    
    # Check budget status
    budget_info = None
    if category.budget_limit:
        now = timezone.now()
        month_total = category.get_total_expenses(
            start_date=now.replace(day=1).date(),
            end_date=now.date()
        )
        budget_info = {
            'limit': category.budget_limit,
            'used': month_total,
            'remaining': category.budget_limit - month_total,
            'percentage': (month_total / category.budget_limit * 100) if category.budget_limit > 0 else 0,
            'is_over': category.is_over_budget()
        }
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'totals': totals,
        'budget_info': budget_info,
    }
    
    return render(request, 'expenses/category_expenses.html', context)


# ============================================================================
# Expense Report Views
# ============================================================================

@login_required
def report_list(request):
    """Display list of expense reports."""
    if request.user.has_perm('expenses.view_all_reports'):
        reports = ExpenseReport.objects.all()
    else:
        reports = ExpenseReport.objects.filter(submitted_by=request.user)
    
    reports = reports.select_related('submitted_by', 'approved_by').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'expenses/report_list.html', context)


@login_required
def report_detail(request, pk):
    """Display expense report details."""
    report = get_object_or_404(ExpenseReport, pk=pk)
    
    # Check permission
    if not (report.submitted_by == request.user or 
            request.user.has_perm('expenses.view_all_reports')):
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('expenses:report_list')
    
    # Get expenses in report
    expenses = report.items.select_related(
        'expense__category', 'expense__submitted_by'
    ).order_by('expense__expense_date')
    
    # Group by category
    category_totals = {}
    for item in expenses:
        category = item.expense.category.name
        if category not in category_totals:
            category_totals[category] = Decimal('0.00')
        category_totals[category] += item.expense.total_amount
    
    context = {
        'report': report,
        'expenses': expenses,
        'category_totals': category_totals,
    }
    
    return render(request, 'expenses/report_detail.html', context)


@login_required
def report_create(request):
    """Create a new expense report."""
    if request.method == 'POST':
        form = ExpenseReportForm(request.POST, user=request.user)
        if form.is_valid():
            report = form.save()
            messages.success(request, f'Report "{report.title}" created successfully.')
            return redirect('expenses:report_add_expenses', pk=report.pk)
    else:
        form = ExpenseReportForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Expense Report',
    }
    
    return render(request, 'expenses/report_form.html', context)


@login_required
def report_add_expenses(request, pk):
    """Add expenses to a report."""
    report = get_object_or_404(ExpenseReport, pk=pk)
    
    # Check permission
    if report.submitted_by != request.user:
        messages.error(request, 'You can only modify your own reports.')
        return redirect('expenses:report_detail', pk=report.pk)
    
    # Get approved expenses in date range
    available_expenses = Expense.objects.filter(
        submitted_by=request.user,
        status='APPROVED',
        expense_date__gte=report.start_date,
        expense_date__lte=report.end_date
    ).exclude(
        report_items__report=report
    ).select_related('category')
    
    if request.method == 'POST':
        expense_ids = request.POST.getlist('expense_ids')
        if expense_ids:
            try:
                report.add_expenses(expense_ids)
                messages.success(request, f'{len(expense_ids)} expense(s) added to report.')
            except Exception as e:
                messages.error(request, f'Error adding expenses: {str(e)}')
        
        return redirect('expenses:report_detail', pk=report.pk)
    
    context = {
        'report': report,
        'available_expenses': available_expenses,
    }
    
    return render(request, 'expenses/report_add_expenses.html', context)


# ============================================================================
# Recurring Expense Views
# ============================================================================

@login_required
def recurring_list(request):
    """Display list of recurring expenses."""
    recurring_expenses = RecurringExpense.objects.filter(
        submitted_by=request.user
    ).select_related('category').order_by('-created_at')
    
    context = {
        'recurring_expenses': recurring_expenses,
    }
    
    return render(request, 'expenses/recurring_list.html', context)


@login_required
def recurring_create(request):
    """Create a recurring expense template."""
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            recurring = form.save()
            messages.success(request, f'Recurring expense "{recurring.title}" created.')
            return redirect('expenses:recurring_list')
    else:
        form = RecurringExpenseForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Recurring Expense',
    }
    
    return render(request, 'expenses/recurring_form.html', context)


@login_required
@require_http_methods(["POST"])
def recurring_generate(request, pk):
    """Generate an expense from recurring template."""
    recurring = get_object_or_404(RecurringExpense, pk=pk)
    
    # Check permission
    if recurring.submitted_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if not recurring.is_active:
        return JsonResponse({
            'error': 'Inactive template',
            'message': 'Cannot generate from inactive template'
        }, status=400)
    
    expense = recurring.generate_expense()
    messages.success(request, f'Expense created from template: {expense.title}')
    
    return JsonResponse({
        'success': True,
        'expense_id': expense.id,
        'message': 'Expense generated successfully.'
    })


# ============================================================================
# Bulk Actions
# ============================================================================

@login_required
@require_http_methods(["POST"])
def bulk_actions(request):
    """Perform bulk actions on expenses."""
    form = BulkExpenseActionForm(request.POST)
    
    if not form.is_valid():
        messages.error(request, 'Invalid action request.')
        return redirect('expenses:expense_list')
    
    expense_ids = form.cleaned_data['expense_ids']
    action = form.cleaned_data['action']
    comments = form.cleaned_data.get('comments', '')
    
    # Get expenses user can modify
    expenses = Expense.objects.filter(pk__in=expense_ids)
    
    # Filter based on action
    if action in ['approve', 'reject']:
        if not request.user.has_perm('expenses.approve_expense'):
            messages.error(request, 'You do not have permission to approve expenses.')
            return redirect('expenses:expense_list')
        expenses = expenses.filter(status='SUBMITTED')
    elif action == 'submit':
        expenses = expenses.filter(submitted_by=request.user, status='DRAFT')
    elif action == 'delete':
        expenses = expenses.filter(submitted_by=request.user, status__in=['DRAFT', 'REJECTED'])
    
    count = expenses.count()
    
    with transaction.atomic():
        if action == 'approve':
            for expense in expenses:
                expense.approve(request.user)
            messages.success(request, f'{count} expense(s) approved.')
        
        elif action == 'reject':
            for expense in expenses:
                expense.reject(request.user, comments)
            messages.success(request, f'{count} expense(s) rejected.')
        
        elif action == 'submit':
            expenses.update(status='SUBMITTED')
            messages.success(request, f'{count} expense(s) submitted for approval.')
        
        elif action == 'delete':
            expenses.delete()
            messages.success(request, f'{count} expense(s) deleted.')
    
    return redirect('expenses:expense_list')


# ============================================================================
# Analytics and Dashboard Views
# ============================================================================

@login_required
def expense_dashboard(request):
    """Display expense analytics dashboard."""
    # Date range for stats (last 12 months)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365)
    
    # User's expenses
    if request.user.has_perm('expenses.view_all_expenses'):
        expenses = Expense.objects.all()
    else:
        expenses = Expense.objects.filter(submitted_by=request.user)
    
    # Overall stats
    stats = {
        'total_expenses': expenses.count(),
        'pending_approval': expenses.filter(status='SUBMITTED').count(),
        'approved': expenses.filter(status='APPROVED').count(),
        'rejected': expenses.filter(status='REJECTED').count(),
        'total_amount': expenses.filter(status='APPROVED').aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or Decimal('0.00'),
    }
    
    # Monthly trend
    from django.db.models.functions import TruncMonth
    monthly_data = expenses.filter(
        expense_date__gte=start_date
    ).annotate(
        month=TruncMonth('expense_date')
    ).values('month').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('month')
    
    # By category
    category_data = expenses.filter(
        status='APPROVED',
        expense_date__gte=start_date
    ).values(
        'category__name'
    ).annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')[:10]
    
    # Recent expenses
    recent_expenses = expenses.select_related(
        'category', 'submitted_by'
    ).order_by('-expense_date')[:10]
    
    context = {
        'stats': stats,
        'monthly_data': list(monthly_data),
        'category_data': list(category_data),
        'recent_expenses': recent_expenses,
    }
    
    return render(request, 'expenses/dashboard.html', context)


# ============================================================================
# API/AJAX Views
# ============================================================================

@login_required
def expense_stats_api(request):
    """Get expense statistics (AJAX)."""
    period = request.GET.get('period', 'month')  # month, quarter, year
    
    end_date = timezone.now().date()
    if period == 'month':
        start_date = end_date.replace(day=1)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    else:  # year
        start_date = end_date - timedelta(days=365)
    
    expenses = Expense.objects.filter(
        submitted_by=request.user,
        expense_date__gte=start_date,
        expense_date__lte=end_date
    )
    
    stats = {
        'total_count': expenses.count(),
        'total_amount': float(expenses.aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0),
        'by_status': {},
        'by_category': {}
    }
    
    # By status
    for status, label in Expense.STATUS_CHOICES:
        count = expenses.filter(status=status).count()
        if count > 0:
            stats['by_status'][label] = count
    
    # By category
    category_stats = expenses.values('category__name').annotate(
        total=Sum('total_amount')
    ).order_by('-total')[:5]
    
    for item in category_stats:
        stats['by_category'][item['category__name']] = float(item['total'])
    
    return JsonResponse(stats)