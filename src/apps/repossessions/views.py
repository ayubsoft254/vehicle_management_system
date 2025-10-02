"""
Views for the repossessions app.
Handles repossession management, tracking, and workflow.
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

from .models import (
    Repossession, RepossessionDocument, RepossessionNote,
    RepossessionExpense, RepossessionStatusHistory, RepossessionNotice,
    RepossessionContact, RepossessionRecoveryAttempt
)
from .forms import (
    RepossessionForm, RepossessionStatusUpdateForm, RepossessionDocumentForm,
    RepossessionNoteForm, RepossessionExpenseForm, RepossessionNoticeForm,
    RepossessionContactForm, RepossessionRecoveryAttemptForm,
    RepossessionSearchForm, RepossessionCompletionForm
)


# ============================================================================
# Dashboard and Overview
# ============================================================================

@login_required
def repossession_dashboard(request):
    """Display repossession dashboard with key metrics."""
    # Status counts
    status_counts = {}
    for status, label in Repossession.STATUS_CHOICES:
        count = Repossession.objects.filter(status=status).count()
        status_counts[status] = {'label': label, 'count': count}
    
    # Recent repossessions
    recent_repos = Repossession.objects.all().select_related(
        'vehicle', 'client', 'assigned_to'
    ).order_by('-created_at')[:10]
    
    # Pending actions
    pending_notices = RepossessionNotice.objects.filter(
        delivered=False
    ).count()
    
    overdue_responses = RepossessionNotice.objects.filter(
        response_deadline__lt=date.today(),
        response_received=False
    ).count()
    
    # Financial summary
    total_outstanding = Repossession.objects.filter(
        status__in=['PENDING', 'NOTICE_SENT', 'IN_PROGRESS', 'VEHICLE_RECOVERED']
    ).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00')
    
    total_costs = Repossession.objects.aggregate(
        Sum('total_cost')
    )['total_cost__sum'] or Decimal('0.00')
    
    # Monthly trend (last 6 months)
    six_months_ago = date.today() - timedelta(days=180)
    monthly_trend = Repossession.objects.filter(
        initiated_date__gte=six_months_ago
    ).extra(
        select={'month': "DATE_TRUNC('month', initiated_date)"}
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    context = {
        'status_counts': status_counts,
        'recent_repos': recent_repos,
        'pending_notices': pending_notices,
        'overdue_responses': overdue_responses,
        'total_outstanding': total_outstanding,
        'total_costs': total_costs,
        'monthly_trend': list(monthly_trend),
    }
    
    return render(request, 'repossessions/dashboard.html', context)


# ============================================================================
# Repossession List and Search
# ============================================================================

@login_required
def repossession_list(request):
    """Display list of repossessions with search and filters."""
    form = RepossessionSearchForm(request.GET or None)
    
    repossessions = Repossession.objects.all().select_related(
        'vehicle', 'client', 'assigned_to', 'created_by'
    )
    
    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        if query:
            repossessions = repossessions.filter(
                Q(repossession_number__icontains=query) |
                Q(vehicle__make__icontains=query) |
                Q(vehicle__model__icontains=query) |
                Q(vehicle__registration_number__icontains=query) |
                Q(client__name__icontains=query) |
                Q(client__email__icontains=query)
            )
        
        status = form.cleaned_data.get('status')
        if status:
            repossessions = repossessions.filter(status=status)
        
        reason = form.cleaned_data.get('reason')
        if reason:
            repossessions = repossessions.filter(reason=reason)
        
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            repossessions = repossessions.filter(initiated_date__gte=date_from)
        
        date_to = form.cleaned_data.get('date_to')
        if date_to:
            repossessions = repossessions.filter(initiated_date__lte=date_to)
        
        assigned_to = form.cleaned_data.get('assigned_to')
        if assigned_to:
            repossessions = repossessions.filter(assigned_to=assigned_to)
    
    # Sort
    sort_by = request.GET.get('sort', '-initiated_date')
    repossessions = repossessions.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(repossessions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_count': paginator.count,
    }
    
    return render(request, 'repossessions/repossession_list.html', context)


# ============================================================================
# Repossession CRUD
# ============================================================================

@login_required
def repossession_detail(request, pk):
    """Display repossession details."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    # Get related data
    documents = repossession.documents.select_related('uploaded_by').order_by('-uploaded_at')
    notes = repossession.notes.select_related('created_by').order_by('-created_at')
    expenses = repossession.expenses.select_related('created_by').order_by('-expense_date')
    status_history = repossession.status_history.select_related('changed_by').order_by('-changed_at')
    notices = repossession.notices.select_related('sent_by').order_by('-notice_date')
    contacts = repossession.contacts.select_related('created_by').order_by('-contact_date')
    recovery_attempts = repossession.recovery_attempts.select_related('created_by').order_by('-attempt_date')
    
    # Calculate summaries
    total_expenses = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    paid_expenses = expenses.filter(paid=True).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    context = {
        'repossession': repossession,
        'documents': documents,
        'notes': notes,
        'expenses': expenses,
        'status_history': status_history,
        'notices': notices,
        'contacts': contacts,
        'recovery_attempts': recovery_attempts,
        'total_expenses': total_expenses,
        'paid_expenses': paid_expenses,
        'days_in_process': repossession.get_days_in_process(),
    }
    
    return render(request, 'repossessions/repossession_detail.html', context)


@login_required
def repossession_create(request):
    """Create a new repossession."""
    if request.method == 'POST':
        form = RepossessionForm(request.POST, user=request.user)
        if form.is_valid():
            repossession = form.save()
            messages.success(
                request,
                f'Repossession {repossession.repossession_number} created successfully.'
            )
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Initiate Repossession',
    }
    
    return render(request, 'repossessions/repossession_form.html', context)


@login_required
def repossession_update(request, pk):
    """Update repossession details."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    if request.method == 'POST':
        form = RepossessionForm(request.POST, instance=repossession, user=request.user)
        if form.is_valid():
            repossession = form.save()
            messages.success(request, 'Repossession updated successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionForm(instance=repossession, user=request.user)
    
    context = {
        'form': form,
        'repossession': repossession,
        'title': 'Edit Repossession',
    }
    
    return render(request, 'repossessions/repossession_form.html', context)


@login_required
def repossession_delete(request, pk):
    """Delete a repossession."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    if not repossession.can_cancel():
        messages.error(request, 'Cannot delete completed or cancelled repossessions.')
        return redirect('repossessions:repossession_detail', pk=repossession.pk)
    
    if request.method == 'POST':
        number = repossession.repossession_number
        repossession.delete()
        messages.success(request, f'Repossession {number} deleted successfully.')
        return redirect('repossessions:repossession_list')
    
    context = {
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/repossession_confirm_delete.html', context)


# ============================================================================
# Status Management
# ============================================================================

@login_required
def repossession_update_status(request, pk):
    """Update repossession status."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    if request.method == 'POST':
        form = RepossessionStatusUpdateForm(request.POST, repossession=repossession)
        if form.is_valid():
            old_status = repossession.status
            new_status = form.cleaned_data['status']
            reason = form.cleaned_data.get('reason', '')
            
            # Update status
            repossession.status = new_status
            repossession.save()
            
            # Create status history
            RepossessionStatusHistory.objects.create(
                repossession=repossession,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                reason=reason
            )
            
            messages.success(request, f'Status updated to {repossession.get_status_display()}.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionStatusUpdateForm(repossession=repossession)
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/status_update.html', context)


@login_required
def repossession_complete(request, pk):
    """Complete a repossession."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    if request.method == 'POST':
        form = RepossessionCompletionForm(request.POST)
        if form.is_valid():
            repossession.mark_as_completed(
                resolution_type=form.cleaned_data['resolution_type'],
                notes=form.cleaned_data['resolution_notes']
            )
            
            messages.success(request, 'Repossession marked as completed.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionCompletionForm()
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/repossession_complete.html', context)


# ============================================================================
# Document Management
# ============================================================================

@login_required
def document_upload(request, repossession_pk):
    """Upload document for repossession."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    if request.method == 'POST':
        form = RepossessionDocumentForm(
            request.POST,
            request.FILES,
            repossession=repossession,
            user=request.user
        )
        if form.is_valid():
            document = form.save()
            messages.success(request, 'Document uploaded successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionDocumentForm(repossession=repossession, user=request.user)
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/document_upload.html', context)


@login_required
@require_http_methods(["POST"])
def document_delete(request, pk):
    """Delete a document."""
    document = get_object_or_404(RepossessionDocument, pk=pk)
    repossession_pk = document.repossession.pk
    
    document.delete()
    messages.success(request, 'Document deleted successfully.')
    
    return JsonResponse({
        'success': True,
        'message': 'Document deleted successfully.'
    })


# ============================================================================
# Notes Management
# ============================================================================

@login_required
@require_http_methods(["POST"])
def note_create(request, repossession_pk):
    """Add note to repossession."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    form = RepossessionNoteForm(
        request.POST,
        repossession=repossession,
        user=request.user
    )
    
    if form.is_valid():
        note = form.save()
        
        return JsonResponse({
            'success': True,
            'note': {
                'id': note.id,
                'note': note.note,
                'note_type': note.get_note_type_display() if note.note_type else '',
                'is_important': note.is_important,
                'created_by': note.created_by.get_full_name() if note.created_by else '',
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            }
        })
    
    return JsonResponse({'error': 'Invalid form data'}, status=400)


@login_required
@require_http_methods(["POST"])
def note_delete(request, pk):
    """Delete a note."""
    note = get_object_or_404(RepossessionNote, pk=pk)
    
    # Check permission
    if note.created_by != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    note.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Note deleted successfully.'
    })


# ============================================================================
# Expense Management
# ============================================================================

@login_required
def expense_create(request, repossession_pk):
    """Add expense to repossession."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    if request.method == 'POST':
        form = RepossessionExpenseForm(
            request.POST,
            repossession=repossession,
            user=request.user
        )
        if form.is_valid():
            expense = form.save()
            messages.success(request, 'Expense added successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionExpenseForm(repossession=repossession, user=request.user)
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/expense_form.html', context)


# ============================================================================
# Notice Management
# ============================================================================

@login_required
def notice_create(request, repossession_pk):
    """Send notice for repossession."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    if request.method == 'POST':
        form = RepossessionNoticeForm(
            request.POST,
            repossession=repossession,
            user=request.user
        )
        if form.is_valid():
            notice = form.save()
            
            # Update repossession status if first notice
            if notice.notice_type == 'FIRST_NOTICE' and repossession.status == 'PENDING':
                repossession.status = 'NOTICE_SENT'
                repossession.notice_sent_date = notice.notice_date
                repossession.save()
            
            messages.success(request, 'Notice sent successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        # Pre-fill delivery address from client
        initial_data = {
            'notice_date': date.today(),
            'delivery_address': repossession.client.address if hasattr(repossession.client, 'address') else '',
        }
        form = RepossessionNoticeForm(
            repossession=repossession,
            user=request.user,
            initial=initial_data
        )
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/notice_form.html', context)


@login_required
@require_http_methods(["POST"])
def notice_mark_delivered(request, pk):
    """Mark notice as delivered."""
    notice = get_object_or_404(RepossessionNotice, pk=pk)
    
    notice.delivered = True
    notice.delivery_date = date.today()
    notice.received_by = request.POST.get('received_by', '')
    notice.save()
    
    messages.success(request, 'Notice marked as delivered.')
    
    return JsonResponse({
        'success': True,
        'message': 'Notice marked as delivered.'
    })


# ============================================================================
# Contact Management
# ============================================================================

@login_required
def contact_create(request, repossession_pk):
    """Record client contact."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    if request.method == 'POST':
        form = RepossessionContactForm(
            request.POST,
            repossession=repossession,
            user=request.user
        )
        if form.is_valid():
            contact = form.save()
            messages.success(request, 'Contact recorded successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionContactForm(repossession=repossession, user=request.user)
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/contact_form.html', context)


# ============================================================================
# Recovery Attempt Management
# ============================================================================

@login_required
def recovery_attempt_create(request, repossession_pk):
    """Record recovery attempt."""
    repossession = get_object_or_404(Repossession, pk=repossession_pk)
    
    if request.method == 'POST':
        form = RepossessionRecoveryAttemptForm(
            request.POST,
            repossession=repossession,
            user=request.user
        )
        if form.is_valid():
            attempt = form.save()
            messages.success(request, 'Recovery attempt recorded.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
    else:
        form = RepossessionRecoveryAttemptForm(
            repossession=repossession,
            user=request.user
        )
    
    context = {
        'form': form,
        'repossession': repossession,
    }
    
    return render(request, 'repossessions/recovery_attempt_form.html', context)


# ============================================================================
# Reports and Analytics
# ============================================================================

@login_required
def repossession_reports(request):
    """Display repossession reports and analytics."""
    # Summary statistics
    total_repos = Repossession.objects.count()
    active_repos = Repossession.objects.exclude(
        status__in=['COMPLETED', 'CANCELLED']
    ).count()
    
    # By status
    by_status = []
    for status, label in Repossession.STATUS_CHOICES:
        count = Repossession.objects.filter(status=status).count()
        by_status.append({
            'status': label,
            'count': count,
        })
    
    # By reason
    by_reason = []
    for reason, label in Repossession.REASON_CHOICES:
        count = Repossession.objects.filter(reason=reason).count()
        by_reason.append({
            'reason': label,
            'count': count,
        })
    
    # Financial summary
    financial_summary = Repossession.objects.aggregate(
        total_outstanding=Sum('outstanding_amount'),
        total_costs=Sum('total_cost'),
        avg_outstanding=Avg('outstanding_amount'),
    )
    
    # Average days to completion
    completed = Repossession.objects.filter(status='COMPLETED')
    avg_days = 0
    if completed.exists():
        total_days = sum([r.get_days_in_process() for r in completed])
        avg_days = total_days / completed.count()
    
    context = {
        'total_repos': total_repos,
        'active_repos': active_repos,
        'by_status': by_status,
        'by_reason': by_reason,
        'financial_summary': financial_summary,
        'avg_days': round(avg_days, 1),
    }
    
    return render(request, 'repossessions/reports.html', context)


# ============================================================================
# API/AJAX Views
# ============================================================================

@login_required
def repossession_timeline(request, pk):
    """Get timeline data for repossession (AJAX)."""
    repossession = get_object_or_404(Repossession, pk=pk)
    
    timeline = []
    
    # Status changes
    for history in repossession.status_history.all():
        timeline.append({
            'date': history.changed_at.isoformat(),
            'type': 'status_change',
            'description': f'Status changed from {history.old_status} to {history.new_status}',
            'user': history.changed_by.get_full_name() if history.changed_by else '',
        })
    
    # Notices
    for notice in repossession.notices.all():
        timeline.append({
            'date': notice.notice_date.isoformat(),
            'type': 'notice',
            'description': f'{notice.get_notice_type_display()} sent via {notice.get_delivery_method_display()}',
            'user': notice.sent_by.get_full_name() if notice.sent_by else '',
        })
    
    # Recovery attempts
    for attempt in repossession.recovery_attempts.all():
        timeline.append({
            'date': attempt.attempt_date.isoformat(),
            'type': 'recovery_attempt',
            'description': f'Recovery attempt: {attempt.get_result_display()}',
            'user': attempt.created_by.get_full_name() if attempt.created_by else '',
        })
    
    # Sort by date
    timeline.sort(key=lambda x: x['date'], reverse=True)
    
    return JsonResponse({'timeline': timeline})