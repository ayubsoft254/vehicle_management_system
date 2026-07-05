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
from dateutil.relativedelta import relativedelta

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import inch

from apps.clients.models import ClientVehicle
from utils.constants import VehicleStatus

from .models import (
    Repossession, RepossessionDocument, RepossessionNote,
    RepossessionExpense, RepossessionStatusHistory, RepossessionNotice,
    RepossessionContact, RepossessionRecoveryAttempt, RepossessionAdditionalCost
)
from .forms import (
    RepossessionForm, RepossessionStatusUpdateForm, RepossessionDocumentForm,
    RepossessionNoteForm, RepossessionExpenseForm, RepossessionNoticeForm,
    RepossessionContactForm, RepossessionRecoveryAttemptForm,
    RepossessionSearchForm, RepossessionCompletionForm
)


def _recalculate_client_debt(client):
    """Keep client debt aligned with active unpaid vehicle balances."""
    current_debt = client.vehicles.filter(is_active=True, is_paid_off=False).aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    client.current_debt = current_debt
    client.save(update_fields=['current_debt'])


def _stop_installment_plan(client_vehicle):
    """Deactivate the installment plan and remove unpaid future schedules."""
    try:
        plan = client_vehicle.installment_plan
        plan.payment_schedules.filter(is_paid=False).delete()
        plan.is_active = False
        plan.save(update_fields=['is_active'])
    except Exception:
        pass


def _mark_client_defaulted(client):
    """Set client status to Repossessed if they have no remaining active vehicles."""
    from utils.constants import ClientStatus
    has_active = client.vehicles.filter(is_active=True).exists()
    if not has_active and client.status not in (ClientStatus.REPOSSESSED, ClientStatus.COMPLETED):
        client.status = ClientStatus.REPOSSESSED
        client.save(update_fields=['status'])


def _apply_repossessed_vehicle_pricing(repossession):
    """When repossession starts, reprices the vehicle to debt + newly added additional costs."""
    vehicle = repossession.vehicle
    new_price = (repossession.outstanding_amount or Decimal('0.00')) + (repossession.additional_costs or Decimal('0.00'))
    vehicle.selling_price = new_price
    vehicle.status = VehicleStatus.REPOSSESSED
    vehicle.save(update_fields=['selling_price', 'status'])


def _extract_additional_cost_entries(post_data):
    """Extract additional categorized cost entries from submitted arrays."""
    categories = post_data.getlist('additional_cost_category[]')
    descriptions = post_data.getlist('additional_cost_description[]')
    amounts = post_data.getlist('additional_cost_amount[]')

    entries = []
    total = Decimal('0.00')

    for category, description, amount_str in zip(categories, descriptions, amounts):
        category = (category or '').strip()
        description = (description or '').strip()
        amount_raw = (amount_str or '').strip()

        if not category and not description and not amount_raw:
            continue

        if not category or not description or not amount_raw:
            continue

        try:
            amount = Decimal(amount_raw)
        except Exception:
            continue

        if amount <= 0:
            continue

        entries.append({
            'category': category,
            'description': description,
            'amount': amount,
        })
        total += amount

    return entries, total


def _sync_additional_cost_items(repossession, entries, user):
    """Sync additional-cost line items and keep aggregate additional_costs field in sync."""
    existing_items = list(repossession.additional_cost_items.order_by('created_at'))

    for index, entry in enumerate(entries):
        category = entry['category']
        description = entry['description']
        amount = entry['amount']
        if index < len(existing_items):
            item = existing_items[index]
            item.category = category
            item.description = description
            item.amount = amount
            item.created_by = user
            item.save(update_fields=['category', 'description', 'amount', 'created_by'])
        else:
            RepossessionAdditionalCost.objects.create(
                repossession=repossession,
                category=category,
                description=description,
                amount=amount,
                created_by=user,
            )

    for item in existing_items[len(entries):]:
        item.delete()

    repossession.additional_costs = sum((entry['amount'] for entry in entries), Decimal('0.00'))
    repossession.save()


def _calculate_repossession_prefill(purchase, as_of_date=None):
    """Build repossession prefill values from client vehicle payment history and schedule."""
    as_of = as_of_date or timezone.now().date()

    outstanding_amount = purchase.balance or Decimal('0.00')
    if outstanding_amount < Decimal('0.00'):
        outstanding_amount = Decimal('0.00')

    last_payment = purchase.payments.order_by('-payment_date', '-created_at').first()
    last_payment_date = last_payment.payment_date if last_payment else None

    payments_missed = 0
    plan = getattr(purchase, 'installment_plan', None)
    if plan:
        payments_missed = plan.payment_schedules.filter(
            is_paid=False,
            due_date__lt=as_of,
        ).count()
    elif purchase.installment_months and purchase.installment_months > 0:
        payment_type = purchase.payment_type or 'installment'
        if payment_type != 'full':
            elapsed_periods = 0
            purchase_date = purchase.purchase_date or as_of

            if purchase.remainder_payment_type == 'weekly':
                elapsed_periods = max((as_of - purchase_date).days // 7, 0)
            else:
                delta = relativedelta(as_of, purchase_date)
                elapsed_periods = max((delta.years * 12) + delta.months, 0)

            expected_periods = min(elapsed_periods, purchase.installment_months)

            paid_installments = 0
            if purchase.monthly_installment and purchase.monthly_installment > 0:
                paid_towards_installments = (purchase.total_paid or Decimal('0.00')) - (purchase.deposit_paid or Decimal('0.00'))
                if paid_towards_installments > 0:
                    paid_installments = int(paid_towards_installments / purchase.monthly_installment)

            payments_missed = max(expected_periods - paid_installments, 0)

    return {
        'outstanding_amount': str(outstanding_amount.quantize(Decimal('0.01'))),
        'payments_missed': int(payments_missed),
        'last_payment_date': last_payment_date.isoformat() if last_payment_date else '',
    }


def _build_vehicle_prefill_map(vehicle_queryset):
    """Create a map keyed by vehicle_id with client + financial prefill data."""
    purchase_qs = ClientVehicle.objects.filter(
        vehicle__in=vehicle_queryset
    ).select_related('client').order_by('vehicle_id', '-is_active', '-purchase_date', '-created_at')

    map_data = {}
    seen = set()
    for purchase in purchase_qs:
        vehicle_id = str(purchase.vehicle_id)
        if vehicle_id in seen:
            continue
        seen.add(vehicle_id)

        financial_prefill = _calculate_repossession_prefill(purchase)
        map_data[vehicle_id] = {
            'client_id': purchase.client_id,
            'client_name': purchase.client.get_full_name(),
            **financial_prefill,
        }

    return map_data


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
    notes = repossession.activity_notes.select_related('created_by').order_by('-created_at')
    expenses = repossession.expenses.select_related('created_by').order_by('-expense_date')
    status_history = repossession.status_history.select_related('changed_by').order_by('-changed_at')
    notices = repossession.notices.select_related('sent_by').order_by('-notice_date')
    contacts = repossession.contacts.select_related('created_by').order_by('-contact_date')
    recovery_attempts = repossession.recovery_attempts.select_related('created_by').order_by('-attempt_date')
    additional_cost_items = repossession.additional_cost_items.all()
    
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
        'additional_cost_items': additional_cost_items,
        'total_expenses': total_expenses,
        'paid_expenses': paid_expenses,
        'total_additional_costs': repossession.get_total_additional_costs(),
        'recovery_target_amount': repossession.outstanding_amount + repossession.get_total_additional_costs(),
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
            additional_cost_entries, _ = _extract_additional_cost_entries(request.POST)
            _sync_additional_cost_items(repossession, additional_cost_entries, request.user)
            _apply_repossessed_vehicle_pricing(repossession)
            messages.success(
                request,
                f'Repossession {repossession.repossession_number} created successfully.'
            )
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
        messages.error(request, 'Repossession could not be created. Please correct the highlighted errors and try again.')
    else:
        initial = {}
        vehicle_id = request.GET.get('vehicle')
        if vehicle_id:
            purchase = ClientVehicle.objects.filter(
                vehicle_id=vehicle_id,
                vehicle__status=VehicleStatus.SOLD,
            ).select_related('client').order_by('-is_active', '-purchase_date', '-created_at').first()
            if purchase:
                initial['vehicle'] = purchase.vehicle_id
                initial['client'] = purchase.client_id
                financial_prefill = _calculate_repossession_prefill(purchase)
                if Decimal(financial_prefill['outstanding_amount']) > Decimal('0.00'):
                    initial['outstanding_amount'] = financial_prefill['outstanding_amount']
                initial['payments_missed'] = financial_prefill['payments_missed']
                if financial_prefill['last_payment_date']:
                    initial['last_payment_date'] = financial_prefill['last_payment_date']

        form = RepossessionForm(user=request.user, initial=initial)
    
    if request.method == 'POST':
        additional_cost_entries, _ = _extract_additional_cost_entries(request.POST)
    else:
        additional_cost_entries = []

    vehicle_prefill_map = _build_vehicle_prefill_map(form.fields['vehicle'].queryset)

    context = {
        'form': form,
        'title': 'Initiate Repossession',
        'vehicle_prefill_map': vehicle_prefill_map,
        'additional_cost_entries': additional_cost_entries,
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
            additional_cost_entries, _ = _extract_additional_cost_entries(request.POST)
            _sync_additional_cost_items(repossession, additional_cost_entries, request.user)
            _apply_repossessed_vehicle_pricing(repossession)
            messages.success(request, 'Repossession updated successfully.')
            return redirect('repossessions:repossession_detail', pk=repossession.pk)
        messages.error(request, 'Repossession could not be updated. Please correct the highlighted errors and try again.')
        additional_cost_entries = _extract_additional_cost_entries(request.POST)[0]
    else:
        form = RepossessionForm(instance=repossession, user=request.user)
        additional_cost_entries = repossession.additional_cost_items.all().order_by('created_at')
    
    context = {
        'form': form,
        'repossession': repossession,
        'title': 'Edit Repossession',
        'vehicle_prefill_map': _build_vehicle_prefill_map(form.fields['vehicle'].queryset),
        'additional_cost_entries': additional_cost_entries,
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
            resolution_type = form.cleaned_data['resolution_type']
            resolution_notes = form.cleaned_data['resolution_notes']
            completion_date = form.cleaned_data['completion_date']

            client_vehicle = ClientVehicle.objects.filter(
                client=repossession.client,
                vehicle=repossession.vehicle,
                is_active=True,
            ).order_by('-purchase_date', '-created_at').first()

            if resolution_type == 'RETURNED' and not client_vehicle:
                messages.error(
                    request,
                    'Cannot return vehicle to client because no active client-vehicle record was found.'
                )
                context = {
                    'form': form,
                    'repossession': repossession,
                }
                return render(request, 'repossessions/repossession_complete.html', context)

            with transaction.atomic():
                base_balance = repossession.outstanding_amount or Decimal('0.00')
                accumulated_costs = repossession.get_total_additional_costs()
                target_price = base_balance + accumulated_costs

                vehicle = repossession.vehicle
                vehicle.selling_price = target_price

                if resolution_type == 'AUCTIONED':
                    vehicle.status = VehicleStatus.AUCTIONED
                    if client_vehicle:
                        client_vehicle.balance = Decimal('0.00')
                        client_vehicle.is_paid_off = True
                        client_vehicle.is_active = False
                        client_vehicle.date_paid_off = completion_date
                        client_vehicle.save(update_fields=['balance', 'is_paid_off', 'is_active', 'date_paid_off'])
                        _stop_installment_plan(client_vehicle)
                        _recalculate_client_debt(repossession.client)
                        _mark_client_defaulted(repossession.client)
                elif resolution_type == 'RETURNED':
                    vehicle.status = VehicleStatus.SOLD
                    client_vehicle.purchase_price = (client_vehicle.purchase_price or Decimal('0.00')) + accumulated_costs
                    client_vehicle.balance = client_vehicle.purchase_price - (client_vehicle.total_paid or Decimal('0.00'))
                    if client_vehicle.balance <= Decimal('0.00'):
                        client_vehicle.balance = Decimal('0.00')
                        client_vehicle.is_paid_off = True
                        client_vehicle.date_paid_off = completion_date
                    else:
                        client_vehicle.is_paid_off = False
                        client_vehicle.date_paid_off = None
                    client_vehicle.is_active = True
                    client_vehicle.save(update_fields=['purchase_price', 'balance', 'is_paid_off', 'date_paid_off', 'is_active'])
                    _recalculate_client_debt(repossession.client)
                else:
                    # Vehicle fully repossessed — deactivate the client record and stop future schedules
                    vehicle.status = VehicleStatus.REPOSSESSED
                    if client_vehicle:
                        client_vehicle.is_active = False
                        client_vehicle.save(update_fields=['is_active'])
                        _stop_installment_plan(client_vehicle)
                        _recalculate_client_debt(repossession.client)
                        _mark_client_defaulted(repossession.client)

                vehicle.save(update_fields=['selling_price', 'status'])

                repossession.status = 'COMPLETED'
                repossession.completion_date = completion_date
                repossession.resolution_type = resolution_type
                repossession.resolution_notes = resolution_notes
                repossession.save(update_fields=['status', 'completion_date', 'resolution_type', 'resolution_notes'])
            
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

def _compute_repossession_report_context(request):
    """Repossession analytics — shared by the on-screen report and its
    PDF/Excel/CSV exports."""
    today = date.today()

    all_repos = Repossession.objects.all()
    total_repos = all_repos.count()
    completed_repos = all_repos.filter(status='COMPLETED')
    cancelled_repos = all_repos.filter(status='CANCELLED')
    active_repos = all_repos.exclude(status__in=['COMPLETED', 'CANCELLED'])

    # Recovery rate: cases where vehicle was actually recovered (status VEHICLE_RECOVERED or COMPLETED with recovery_date)
    recovered_count = all_repos.filter(
        status__in=['VEHICLE_RECOVERED', 'COMPLETED']
    ).exclude(recovery_date=None).count()

    # By status with outstanding amounts
    by_status = []
    for status, label in Repossession.STATUS_CHOICES:
        qs = all_repos.filter(status=status)
        agg = qs.aggregate(
            count=Count('id'),
            total_outstanding=Sum('outstanding_amount'),
        )
        by_status.append({
            'status': label,
            'value': status,
            'count': agg['count'] or 0,
            'total_outstanding': agg['total_outstanding'] or 0,
        })

    # By reason
    by_reason = []
    for reason, label in Repossession.REASON_CHOICES:
        count = all_repos.filter(reason=reason).count()
        by_reason.append({'reason': label, 'count': count})

    # Financial summary
    financial_summary = all_repos.aggregate(
        total_outstanding=Sum('outstanding_amount'),
        total_costs=Sum('total_cost'),
        avg_outstanding=Avg('outstanding_amount'),
        total_recovery_cost=Sum('recovery_cost'),
        total_legal_cost=Sum('legal_cost'),
        total_storage_cost=Sum('storage_cost'),
    )

    # Active outstanding by age bucket
    age_buckets = [
        {'label': '0–30 days', 'min': 0, 'max': 30, 'count': 0, 'outstanding': 0},
        {'label': '31–60 days', 'min': 31, 'max': 60, 'count': 0, 'outstanding': 0},
        {'label': '61–90 days', 'min': 61, 'max': 90, 'count': 0, 'outstanding': 0},
        {'label': '91+ days', 'min': 91, 'max': None, 'count': 0, 'outstanding': 0},
    ]
    for repo in active_repos.only('initiated_date', 'outstanding_amount'):
        age = (today - repo.initiated_date).days
        for bucket in age_buckets:
            if bucket['max'] is None and age >= bucket['min']:
                bucket['count'] += 1
                bucket['outstanding'] += float(repo.outstanding_amount or 0)
                break
            elif bucket['max'] is not None and bucket['min'] <= age <= bucket['max']:
                bucket['count'] += 1
                bucket['outstanding'] += float(repo.outstanding_amount or 0)
                break

    # Agent breakdown (assigned_to)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    agent_breakdown = (
        all_repos.filter(assigned_to__isnull=False)
        .values('assigned_to__first_name', 'assigned_to__last_name', 'assigned_to__id')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
            active=Count('id', filter=~Q(status__in=['COMPLETED', 'CANCELLED'])),
            outstanding=Sum('outstanding_amount', filter=~Q(status__in=['COMPLETED', 'CANCELLED'])),
        )
        .order_by('-total')[:10]
    )

    # Average days to completion
    avg_days = 0
    if completed_repos.exists():
        total_days = sum([r.get_days_in_process() for r in completed_repos])
        avg_days = total_days / completed_repos.count()

    # Recent active cases (latest 10)
    recent_cases = active_repos.select_related('client', 'vehicle', 'assigned_to').order_by('-initiated_date')[:10]

    # This month new cases
    month_start = today.replace(day=1)
    this_month_count = all_repos.filter(initiated_date__gte=month_start).count()

    context = {
        'total_repos': total_repos,
        'active_repos': active_repos.count(),
        'completed_count': completed_repos.count(),
        'cancelled_count': cancelled_repos.count(),
        'recovered_count': recovered_count,
        'by_status': by_status,
        'by_reason': by_reason,
        'financial_summary': financial_summary,
        'avg_days': round(avg_days, 1),
        'age_buckets': age_buckets,
        'agent_breakdown': agent_breakdown,
        'recent_cases': recent_cases,
        'this_month_count': this_month_count,
        'today': today,
        'all_repos': all_repos.select_related('client', 'vehicle').order_by('-initiated_date'),
    }
    return context


@login_required
def repossession_reports(request):
    context = _compute_repossession_report_context(request)
    return render(request, 'repossessions/reports.html', context)


@login_required
def repossession_reports_pdf(request):
    from utils.report_kit import build_pdf_response, styled_table, kpi_table, fmt_money
    ctx = _compute_repossession_report_context(request)

    def body(elements, styles):
        elements.append(kpi_table([
            ('Total Cases', str(ctx['total_repos'])),
            ('Active', str(ctx['active_repos'])),
            ('Completed', str(ctx['completed_count'])),
            ('Recovered', str(ctx['recovered_count'])),
            ('Total Outstanding', fmt_money(ctx['financial_summary']['total_outstanding'] or 0)),
            ('Total Costs', fmt_money(ctx['financial_summary']['total_costs'] or 0)),
        ]))
        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Cases', styles['ReportSectionHeading']))
        rows = [['Date', 'Client', 'Vehicle', 'Status', 'Outstanding']]
        for r in ctx['all_repos']:
            rows.append([
                r.initiated_date.strftime('%Y-%m-%d'),
                r.client.get_full_name() if r.client else '—',
                r.vehicle.full_name if r.vehicle else '—',
                r.get_status_display(), fmt_money(r.outstanding_amount),
            ])
        elements.append(styled_table(rows, col_widths=[0.9 * inch, 1.8 * inch, 1.8 * inch, 1.3 * inch, 1.2 * inch], align_right_from=4))

    return build_pdf_response('repossession_report.pdf', 'Repossessions Report', build_body=body)


@login_required
def repossession_reports_excel(request):
    from utils.report_kit import build_excel_response
    ctx = _compute_repossession_report_context(request)
    headers = ['Date', 'Client', 'Vehicle', 'Reason', 'Status', 'Outstanding']
    rows = [
        [
            r.initiated_date.strftime('%Y-%m-%d'), r.client.get_full_name() if r.client else '—',
            r.vehicle.full_name if r.vehicle else '—', r.get_reason_display(), r.get_status_display(),
            float(r.outstanding_amount or 0),
        ]
        for r in ctx['all_repos']
    ]
    return build_excel_response('repossession_report.xlsx', 'Repossessions', headers, rows, currency_cols={6})


@login_required
def repossession_reports_csv(request):
    from utils.report_kit import build_csv_response
    ctx = _compute_repossession_report_context(request)
    headers = ['Date', 'Client', 'Vehicle', 'Reason', 'Status', 'Outstanding']
    rows = [
        [
            r.initiated_date.strftime('%Y-%m-%d'), r.client.get_full_name() if r.client else '—',
            r.vehicle.full_name if r.vehicle else '—', r.get_reason_display(), r.get_status_display(),
            r.outstanding_amount or 0,
        ]
        for r in ctx['all_repos']
    ]
    return build_csv_response('repossession_report.csv', headers, rows)


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