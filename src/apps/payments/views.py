"""
Views for the payments app
Handles payment recording, installment plans, schedules, and reporting
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta
import csv
import json
import re

from .models import (
    Payment,
    AccountWithdrawal,
    InstallmentPlan,
    PaymentSchedule,
    PaymentReminder,
    MpesaSTKRequest,
    PaybillTransaction,
    PaybillBalanceSnapshot,
)
from .daraja import (
    request_account_balance, mpesa_is_configured, get_missing_mpesa_vars,
    initiate_stk_push, _normalize_phone_number,
)
from apps.clients.models import Client, ClientVehicle
from apps.audit.utils import log_audit


def _parse_export_currency(request):
    """Read export currency context from query params with safe defaults."""
    currency = (request.GET.get('currency') or 'KES').strip().upper()
    if currency not in {'KES', 'USD'}:
        currency = 'KES'

    if currency == 'KES':
        return currency, Decimal('1.00')

    # Prefer client-provided runtime rate from the UI selector/session.
    rate_raw = (request.GET.get('currency_rate') or '').strip()
    if rate_raw:
        try:
            rate = Decimal(rate_raw)
            if rate > 0:
                return currency, rate
        except (InvalidOperation, TypeError):
            pass

    # Fallback for server-side usage when a runtime rate was not supplied.
    return currency, Decimal('0.0077')


def _convert_kes_amount(amount, fx_rate):
    """Convert amount from KES using supplied FX rate; keep 2 decimal places."""
    value = amount or Decimal('0.00')
    return (value * fx_rate).quantize(Decimal('0.01'))


def _build_due_monitor_stats(today=None):
    """Return live due-date and defaulter metrics for dashboard/reporting widgets."""
    today = today or timezone.now().date()

    due_today_qs = PaymentSchedule.objects.filter(is_paid=False, due_date=today)
    overdue_qs = PaymentSchedule.objects.filter(is_paid=False, due_date__lt=today)

    due_today_amount = due_today_qs.aggregate(total=Sum(F('amount_due') - F('amount_paid')))['total'] or Decimal('0.00')
    overdue_amount = overdue_qs.aggregate(total=Sum(F('amount_due') - F('amount_paid')))['total'] or Decimal('0.00')

    defaulters_count = overdue_qs.values('installment_plan__client_vehicle__client_id').distinct().count()

    top_defaulter_rows = overdue_qs.select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle',
    ).order_by('due_date')[:8]

    top_defaulters = []
    seen_client_vehicle_ids = set()
    for schedule in top_defaulter_rows:
        client_vehicle = schedule.installment_plan.client_vehicle
        if client_vehicle.id in seen_client_vehicle_ids:
            continue
        seen_client_vehicle_ids.add(client_vehicle.id)
        top_defaulters.append({
            'client': client_vehicle.client,
            'vehicle': client_vehicle.vehicle,
            'client_vehicle_id': client_vehicle.id,
            'days_overdue': schedule.days_overdue,
            'remaining_amount': schedule.remaining_amount,
        })

    return {
        'due_today_count': due_today_qs.count(),
        'due_today_amount': due_today_amount,
        'overdue_count': overdue_qs.count(),
        'overdue_amount': overdue_amount,
        'defaulters_count': defaulters_count,
        'top_defaulters': top_defaulters,
        'snapshot_time': timezone.now(),
    }


# ==================== PAYMENT MANAGEMENT VIEWS ====================

@login_required
def payment_list(request):
    """
    Display list of all payments with filtering
    """
    payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'recorded_by'
    ).prefetch_related('splits').order_by('-payment_date')
    
    # Filtering
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    payment_method = request.GET.get('payment_method')
    search = request.GET.get('search')
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    if payment_method:
        payments = payments.filter(
            Q(payment_method=payment_method) |
            Q(splits__payment_method=payment_method)
        ).distinct()
    
    if search:
        payments = payments.filter(
            Q(receipt_number__icontains=search) |
            Q(transaction_reference__icontains=search) |
            Q(client_vehicle__client__first_name__icontains=search) |
            Q(client_vehicle__client__last_name__icontains=search) |
            Q(client_vehicle__vehicle__registration_number__icontains=search)
        )
    
    # Statistics
    total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    payment_count = payments.count()
    
    # This month statistics
    now = timezone.now()
    this_month_payments = Payment.objects.filter(
        payment_date__year=now.year,
        payment_date__month=now.month
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    hoza_methods = {'equity_hoza', 'dib_hoza', 'coop_hoza'}

    hoza_total = Decimal('0.00')
    ke_total = Decimal('0.00')
    cash_total = Decimal('0.00')
    other_total = Decimal('0.00')

    for payment in payments:
        if payment.splits.exists():
            portions = [(split.payment_method, split.amount) for split in payment.splits.all()]
        else:
            portions = [(payment.payment_method, payment.amount)]

        for method, amount in portions:
            method_value = (method or '').lower()
            amt = amount or Decimal('0.00')
            if method_value in hoza_methods:
                hoza_total += amt
            elif method_value.endswith('_ke'):
                ke_total += amt
            elif method_value == 'cash':
                cash_total += amt
            else:
                other_total += amt

    withdrawals = AccountWithdrawal.objects.order_by('-withdrawal_date', '-created_at')
    hoza_withdrawals_total = Decimal('0.00')
    ke_withdrawals_total = Decimal('0.00')

    for withdrawal in withdrawals:
        if withdrawal.is_hoza:
            hoza_withdrawals_total += withdrawal.amount
        elif withdrawal.is_ke:
            ke_withdrawals_total += withdrawal.amount

    adjusted_hoza_total = hoza_total - hoza_withdrawals_total
    adjusted_ke_total = ke_total - ke_withdrawals_total
    recent_withdrawals = withdrawals[:5]

    due_stats = _build_due_monitor_stats()
    
    # Pagination
    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'payments': page_obj,
        'total_payments': total_payments,
        'payment_count': payment_count,
        'this_month_payments': this_month_payments,
        'hoza_total': adjusted_hoza_total,
        'ke_total': adjusted_ke_total,
        'hoza_withdrawals_total': hoza_withdrawals_total,
        'ke_withdrawals_total': ke_withdrawals_total,
        'cash_total': cash_total,
        'other_total': other_total,
        'payment_methods': Payment.PAYMENT_METHOD_CHOICES,
        'recent_withdrawals': recent_withdrawals,
        **due_stats,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed payment list')
    
    return render(request, 'payments/payment_list.html', context)


@login_required
def record_account_withdrawal(request):
    """Record a withdrawal from an HOZA or KE account."""
    from .forms import AccountWithdrawalForm

    if request.method == 'POST':
        form = AccountWithdrawalForm(request.POST)
        if form.is_valid():
            withdrawal = form.save(commit=False)
            withdrawal.recorded_by = request.user
            withdrawal.save()

            messages.success(
                request,
                f'Account withdrawal recorded: KES {withdrawal.amount:,.2f} from {withdrawal.get_payment_method_display()}.'
            )
            log_audit(
                request.user,
                'create',
                'AccountWithdrawal',
                f'Recorded account withdrawal {withdrawal.get_payment_method_display()} for KES {withdrawal.amount:,.2f}'
            )
            return redirect('payments:payment_list')
    else:
        form = AccountWithdrawalForm()

    context = {
        'form': form,
    }

    return render(request, 'payments/account_withdrawal_form.html', context)


@login_required
def account_withdrawal_list(request):
    """Display recorded HOZA / KE account withdrawals."""
    withdrawals = AccountWithdrawal.objects.order_by('-withdrawal_date', '-created_at')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    payment_method = request.GET.get('payment_method')

    if date_from:
        withdrawals = withdrawals.filter(withdrawal_date__gte=date_from)
    if date_to:
        withdrawals = withdrawals.filter(withdrawal_date__lte=date_to)
    if payment_method:
        withdrawals = withdrawals.filter(payment_method=payment_method)

    paginator = Paginator(withdrawals, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'withdrawals': page_obj,
        'payment_methods': AccountWithdrawal.PAYMENT_METHOD_CHOICES,
        'date_from': date_from,
        'date_to': date_to,
        'payment_method': payment_method,
    }

    log_audit(request.user, 'view', 'AccountWithdrawal', 'Viewed account withdrawals list')
    return render(request, 'payments/account_withdrawal_list.html', context)


@login_required
def payment_detail(request, pk):
    """
    Display detailed information about a specific payment
    """
    payment = get_object_or_404(
        Payment.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'recorded_by'
        ),
        pk=pk
    )
    
    context = {
        'payment': payment,
        'client': payment.client_vehicle.client,
        'vehicle': payment.client_vehicle.vehicle,
        'client_vehicle': payment.client_vehicle,
    }
    
    log_audit(request.user, 'view', 'Payment', f'Viewed payment {payment.receipt_number}')
    
    return render(request, 'payments/payment_detail.html', context)


@login_required
def record_payment(request, client_vehicle_pk):
    """
    Record a new payment for a client vehicle
    Supports single payment method or split across multiple methods
    """
    from .forms import PaymentForm
    from .models import PaymentSplit
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    if request.method == 'POST':
        # Check if this is a split payment
        split_methods = request.POST.getlist('split_method[]')
        split_amounts = request.POST.getlist('split_amount[]')
        split_references = request.POST.getlist('split_reference[]')
        split_locations = request.POST.getlist('split_location[]')
        
        # Filter out empty splits
        valid_splits = [
            (m, a, r, loc) for m, a, r, loc in zip(split_methods, split_amounts, split_references, split_locations) 
            if m and a
        ]
        
        if valid_splits and len(valid_splits) > 1:
            # Multi-split payment
            with transaction.atomic():
                try:
                    # Calculate total from splits
                    total_amount = sum(Decimal(a) for _, a, _, _ in valid_splits)
                    
                    # Create main payment with MIXED method
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=request.POST.get('payment_date') or timezone.now().date(),
                        payment_method='mixed',
                        notes=request.POST.get('notes', ''),
                        recorded_by=request.user,
                    )
                    
                    # Create split records
                    for method, amount, reference, location in valid_splits:
                        PaymentSplit.objects.create(
                            payment=payment,
                            payment_method=method,
                            amount=Decimal(amount),
                            transaction_reference=reference or None,
                            payment_location=(location or '').strip() or None,
                        )
                    
                    # Update client vehicle balance
                    client_vehicle.total_paid += payment.amount
                    client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
                    
                    # Check if fully paid
                    if client_vehicle.balance <= 0:
                        client_vehicle.is_paid_off = True
                        client_vehicle.client.status = 'completed'
                        client_vehicle.client.save()
                        
                        messages.success(
                            request,
                            f'Split payment recorded! Vehicle fully paid off! 🎉'
                        )
                    else:
                        split_summary = ', '.join([
                            f"{Payment.PAYMENT_METHOD_CHOICES[
                                [x[0] for x in Payment.PAYMENT_METHOD_CHOICES].index(m)
                            ][1]} KES {a:,.2f}"
                            for m, a, _, _ in valid_splits
                        ])
                        messages.success(
                            request,
                            f'Split payment of KES {payment.amount:,.2f} recorded! '
                            f'({split_summary}) — '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )
                    
                    client_vehicle.save()
                    
                    # Update payment schedule if exists
                    update_payment_schedules(payment, client_vehicle)
                    
                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )
                    
                    return redirect('payments:payment_detail', pk=payment.pk)
                    
                except (ValueError, Decimal.InvalidOperation) as e:
                    messages.error(request, f'Invalid split amounts: {str(e)}')
        else:
            # Single payment (traditional flow)
            form = PaymentForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.client_vehicle = client_vehicle
                    payment.recorded_by = request.user
                    payment.save()
                    
                    # Update client vehicle balance
                    client_vehicle.total_paid += payment.amount
                    client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
                    
                    # Check if fully paid
                    if client_vehicle.balance <= 0:
                        client_vehicle.is_paid_off = True
                        client_vehicle.client.status = 'completed'
                        client_vehicle.client.save()
                        
                        messages.success(
                            request,
                            f'Payment recorded! Vehicle fully paid off! 🎉'
                        )
                    else:
                        messages.success(
                            request,
                            f'Payment of KES {payment.amount:,.2f} recorded successfully! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )
                    
                    client_vehicle.save()
                    
                    # Update payment schedule if exists
                    update_payment_schedules(payment, client_vehicle)
                    
                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )
                    
                    return redirect('payments:payment_detail', pk=payment.pk)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(initial={'client_vehicle': client_vehicle})
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
    }
    
    return render(request, 'payments/payment_form.html', context)


@login_required
def quick_record_payment(request):
    """
    Quick payment recording - select client/vehicle first
    Can be accessed from dashboard or admin panel
    Supports single payment or split across multiple methods
    """
    from .forms import PaymentForm
    from .models import PaymentSplit
    
    if request.method == 'POST':
        # Check if this is a split payment
        split_methods = request.POST.getlist('split_method[]')
        split_amounts = request.POST.getlist('split_amount[]')
        split_references = request.POST.getlist('split_reference[]')
        split_locations = request.POST.getlist('split_location[]')
        
        # Filter out empty splits
        valid_splits = [
            (m, a, r, loc) for m, a, r, loc in zip(split_methods, split_amounts, split_references, split_locations) 
            if m and a
        ]
        
        if valid_splits and len(valid_splits) > 1:
            # Multi-split payment
            with transaction.atomic():
                try:
                    client_vehicle_id = request.POST.get('client_vehicle')
                    client_vehicle = ClientVehicle.objects.get(pk=client_vehicle_id)
                    
                    # Calculate total from splits
                    total_amount = sum(Decimal(a) for _, a, _, _ in valid_splits)
                    
                    # Create main payment with MIXED method
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=request.POST.get('payment_date') or timezone.now().date(),
                        payment_method='mixed',
                        notes=request.POST.get('notes', ''),
                        recorded_by=request.user,
                    )
                    
                    # Create split records
                    for method, amount, reference, location in valid_splits:
                        PaymentSplit.objects.create(
                            payment=payment,
                            payment_method=method,
                            amount=Decimal(amount),
                            transaction_reference=reference or None,
                            payment_location=(location or '').strip() or None,
                        )
                    
                    # Update client vehicle balance
                    client_vehicle.total_paid += payment.amount
                    client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
                    
                    # Check if fully paid
                    if client_vehicle.balance <= 0:
                        client_vehicle.is_paid_off = True
                        client_vehicle.client.status = 'completed'
                        client_vehicle.client.save()
                        
                        messages.success(request, f'Split payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Split payment of KES {payment.amount:,.2f} recorded! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )
                    
                    client_vehicle.save()
                    
                    # Update payment schedule if exists
                    update_payment_schedules(payment, client_vehicle)
                    
                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )
                    
                    return redirect('payments:payment_detail', pk=payment.pk)
                    
                except (ValueError, Decimal.InvalidOperation, ClientVehicle.DoesNotExist) as e:
                    messages.error(request, f'Error processing split payment: {str(e)}')
        else:
            # Single payment (traditional flow)
            form = PaymentForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.recorded_by = request.user
                    payment.save()
                    
                    # Update client vehicle balance
                    client_vehicle = payment.client_vehicle
                    client_vehicle.total_paid += payment.amount
                    client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
                    
                    # Check if fully paid
                    if client_vehicle.balance <= 0:
                        client_vehicle.is_paid_off = True
                        client_vehicle.client.status = 'completed'
                        client_vehicle.client.save()
                        
                        messages.success(request, f'Payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Payment of KES {payment.amount:,.2f} recorded successfully! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )
                    
                    client_vehicle.save()
                    
                    # Update payment schedule if exists
                    update_payment_schedules(payment, client_vehicle)
                    
                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )
                    
                    return redirect('payments:payment_detail', pk=payment.pk)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-select client_vehicle if passed in GET parameter
        client_vehicle_id = request.GET.get('client_vehicle')
        initial = {}
        client_vehicle = None
        
        if client_vehicle_id:
            try:
                client_vehicle = ClientVehicle.objects.select_related('client', 'vehicle').get(pk=client_vehicle_id)
                initial['client_vehicle'] = client_vehicle
            except ClientVehicle.DoesNotExist:
                pass
        
        form = PaymentForm(initial=initial)
    
    # Get recent client vehicles with outstanding balances
    recent_client_vehicles = ClientVehicle.objects.select_related(
        'client', 'vehicle'
    ).filter(
        is_paid_off=False,
        balance__gt=0
    ).order_by('-purchase_date')[:20]
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'recent_client_vehicles': recent_client_vehicles,
        'is_quick_record': True,
    }
    
    return render(request, 'payments/quick_payment_form.html', context)


@login_required
def payment_receipt(request, pk):
    """
    Generate and display payment receipt
    """
    payment = get_object_or_404(
        Payment.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'recorded_by'
        ),
        pk=pk
    )
    
    context = {
        'payment': payment,
        'client': payment.client_vehicle.client,
        'vehicle': payment.client_vehicle.vehicle,
        'client_vehicle': payment.client_vehicle,
        'printed_date': timezone.now(),
    }
    
    log_audit(request.user, 'view', 'Payment', f'Generated receipt for {payment.receipt_number}')
    
    return render(request, 'payments/payment_receipt.html', context)


# ==================== INSTALLMENT PLAN VIEWS ====================

@login_required
def installment_plan_list(request):
    """
    Display list of all installment plans
    """
    plans = InstallmentPlan.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'created_by'
    ).order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    
    if status_filter == 'active':
        plans = plans.filter(is_active=True, is_completed=False)
    elif status_filter == 'completed':
        plans = plans.filter(is_completed=True)
    elif status_filter == 'overdue':
        today = timezone.now().date()
        plans = plans.filter(is_active=True, is_completed=False, end_date__lt=today)
    
    if search:
        plans = plans.filter(
            Q(client_vehicle__client__first_name__icontains=search) |
            Q(client_vehicle__client__last_name__icontains=search) |
            Q(client_vehicle__vehicle__registration_number__icontains=search)
        )
    
    # Statistics
    total_plans = plans.count()
    active_plans = plans.filter(is_active=True, is_completed=False).count()
    completed_plans = plans.filter(is_completed=True).count()
    overdue_plans = plans.filter(
        is_active=True,
        is_completed=False,
        end_date__lt=timezone.now().date()
    ).count()
    
    # Pagination
    paginator = Paginator(plans, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'plans': page_obj,
        'total_plans': total_plans,
        'active_plans': active_plans,
        'completed_plans': completed_plans,
        'overdue_plans': overdue_plans,
    }
    
    log_audit(request.user, 'view', 'InstallmentPlan', 'Viewed installment plan list')
    
    return render(request, 'payments/installment_plan_list.html', context)


@login_required
def installment_plan_detail(request, pk):
    """
    Display detailed information about an installment plan
    """
    plan = get_object_or_404(
        InstallmentPlan.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'created_by'
        ),
        pk=pk
    )
    
    # Get payment schedules
    schedules = plan.payment_schedules.all().order_by('installment_number')
    
    # Get all payments for this client vehicle
    payments = Payment.objects.filter(
        client_vehicle=plan.client_vehicle
    ).order_by('-payment_date')
    
    context = {
        'plan': plan,
        'schedules': schedules,
        'payments': payments,
        'client': plan.client_vehicle.client,
        'vehicle': plan.client_vehicle.vehicle,
    }
    
    log_audit(request.user, 'view', 'InstallmentPlan', f'Viewed installment plan {plan.pk}')
    
    return render(request, 'payments/installment_plan_detail.html', context)


@login_required
def create_installment_plan(request, client_vehicle_pk):
    """
    Create a new installment plan
    """
    from .forms import InstallmentPlanForm
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    # Check if plan already exists
    if hasattr(client_vehicle, 'installment_plan'):
        messages.warning(request, 'An installment plan already exists for this vehicle.')
        return redirect('payments:installment_plan_detail', pk=client_vehicle.installment_plan.pk)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.client_vehicle = client_vehicle
                plan.created_by = request.user
                plan.save()
                
                # Generate payment schedules
                plan.generate_payment_schedule()
                
                log_audit(
                    request.user, 'create', 'InstallmentPlan',
                    f'Created installment plan for {client_vehicle.client.get_full_name()}'
                )
                
                messages.success(request, 'Installment plan created successfully!')
                return redirect('payments:installment_plan_detail', pk=plan.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill form with client vehicle data
        initial_data = {
            'total_amount': client_vehicle.purchase_price,
            'deposit': client_vehicle.deposit_paid,
            'monthly_installment': client_vehicle.monthly_installment,
            'number_of_installments': client_vehicle.installment_months,
            'interest_rate': client_vehicle.interest_rate or 0,
            'start_date': client_vehicle.purchase_date,
        }
        form = InstallmentPlanForm(initial=initial_data)
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
    }
    
    return render(request, 'payments/installment_plan_form.html', context)


@login_required
def update_installment_plan(request, pk):
    """
    Update an existing installment plan
    """
    from .forms import InstallmentPlanForm
    
    plan = get_object_or_404(InstallmentPlan, pk=pk)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            
            log_audit(
                request.user, 'update', 'InstallmentPlan',
                f'Updated installment plan {plan.pk}'
            )
            
            messages.success(request, 'Installment plan updated successfully!')
            return redirect('payments:installment_plan_detail', pk=plan.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InstallmentPlanForm(instance=plan)
    
    context = {
        'form': form,
        'plan': plan,
        'client_vehicle': plan.client_vehicle,
    }
    
    return render(request, 'payments/installment_plan_form.html', context)


@login_required
def regenerate_payment_schedule(request, pk):
    """
    Regenerate payment schedule for an installment plan
    """
    plan = get_object_or_404(InstallmentPlan, pk=pk)
    
    if request.method == 'POST':
        plan.generate_payment_schedule()
        
        log_audit(
            request.user, 'update', 'InstallmentPlan',
            f'Regenerated payment schedule for plan {plan.pk}'
        )
        
        messages.success(request, 'Payment schedule regenerated successfully!')
        return redirect('payments:installment_plan_detail', pk=plan.pk)
    
    context = {
        'plan': plan
    }
    
    return render(request, 'payments/confirm_regenerate_schedule.html', context)


@login_required
def extend_installment_plan(request, pk):
    """
    Extend an installment plan by adding months and applying an extension fee.
    The remaining unpaid schedules are re-amortized across the new duration.
    """
    from .forms import InstallmentExtensionForm

    plan = get_object_or_404(
        InstallmentPlan.objects.select_related('client_vehicle__client', 'client_vehicle__vehicle'),
        pk=pk,
    )

    if plan.is_completed:
        messages.error(request, 'Completed plans cannot be extended.')
        return redirect('payments:installment_plan_detail', pk=plan.pk)

    unpaid_schedules = plan.payment_schedules.filter(is_paid=False).order_by('due_date', 'installment_number')

    if not unpaid_schedules.exists():
        messages.error(request, 'No unpaid installments found to extend.')
        return redirect('payments:installment_plan_detail', pk=plan.pk)

    if unpaid_schedules.filter(amount_paid__gt=Decimal('0.00')).exists():
        messages.error(
            request,
            'This plan has partially-paid installments. Clear or settle them before extending the plan.'
        )
        return redirect('payments:installment_plan_detail', pk=plan.pk)

    if request.method == 'POST':
        form = InstallmentExtensionForm(request.POST)
        if form.is_valid():
            extension_months = form.cleaned_data['extension_months']
            extension_fee = form.cleaned_data['extension_fee']
            reason = (form.cleaned_data.get('reason') or '').strip()

            with transaction.atomic():
                unpaid_list = list(unpaid_schedules)
                existing_unpaid_count = len(unpaid_list)
                new_unpaid_count = existing_unpaid_count + extension_months

                existing_unpaid_total = sum((s.amount_due for s in unpaid_list), Decimal('0.00'))
                new_unpaid_total = existing_unpaid_total + extension_fee

                base_due_date = unpaid_list[0].due_date

                # Update plan financials
                plan.number_of_installments = plan.number_of_installments + extension_months
                plan.total_amount = plan.total_amount + extension_fee

                base_monthly = (new_unpaid_total / Decimal(str(new_unpaid_count))).quantize(Decimal('0.01'))
                plan.monthly_installment = base_monthly

                # Remove old unpaid schedules and rebuild them with extended horizon.
                first_new_installment_number = min(s.installment_number for s in unpaid_list)
                unpaid_schedules.delete()

                remainder_type = getattr(plan.client_vehicle, 'remainder_payment_type', 'monthly')
                monthly_date = getattr(plan.client_vehicle, 'monthly_payment_date', None) or base_due_date.day
                weekly_day = getattr(plan.client_vehicle, 'weekly_payment_day', None)

                # Split any rounding remainder into the first installment.
                total_by_equal = base_monthly * new_unpaid_count
                rounding_diff = (new_unpaid_total - total_by_equal).quantize(Decimal('0.01'))

                current_date = base_due_date
                for idx in range(new_unpaid_count):
                    if remainder_type == 'weekly' and weekly_day is not None:
                        if idx == 0:
                            due_date = current_date
                        else:
                            due_date = current_date + timedelta(weeks=1)
                            current_date = due_date
                    else:
                        if idx == 0:
                            due_date = current_date
                        else:
                            candidate = current_date + relativedelta(months=1)
                            try:
                                due_date = candidate.replace(day=int(monthly_date))
                            except ValueError:
                                due_date = candidate + relativedelta(day=31)
                            current_date = due_date

                    amount_due = base_monthly
                    if idx == 0:
                        amount_due = (amount_due + rounding_diff).quantize(Decimal('0.01'))

                    PaymentSchedule.objects.create(
                        installment_plan=plan,
                        installment_number=first_new_installment_number + idx,
                        due_date=due_date,
                        amount_due=amount_due,
                        amount_paid=Decimal('0.00'),
                        is_paid=False,
                    )

                # Keep end_date aligned with rebuilt schedule.
                last_schedule = plan.payment_schedules.order_by('-installment_number').first()
                if last_schedule:
                    plan.end_date = last_schedule.due_date

                note_line = (
                    f"[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Extended by {extension_months} months; "
                    f"fee KES {extension_fee:,.2f}."
                )
                if reason:
                    note_line += f" Reason: {reason}"
                existing_notes = (plan.notes or '').strip()
                plan.notes = f"{existing_notes}\n{note_line}".strip()
                plan.save(update_fields=['number_of_installments', 'total_amount', 'monthly_installment', 'end_date', 'notes', 'updated_at'])

                log_audit(
                    request.user,
                    'update',
                    'InstallmentPlan',
                    f'Extended installment plan {plan.pk} by {extension_months} months with fee KES {extension_fee:,.2f}'
                )

                messages.success(
                    request,
                    f'Installment plan extended by {extension_months} month(s). Extension fee KES {extension_fee:,.2f} applied.'
                )
                return redirect('payments:installment_plan_detail', pk=plan.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InstallmentExtensionForm()

    context = {
        'plan': plan,
        'form': form,
        'client': plan.client_vehicle.client,
        'vehicle': plan.client_vehicle.vehicle,
        'unpaid_count': unpaid_schedules.count(),
        'unpaid_total': unpaid_schedules.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00'),
    }

    return render(request, 'payments/extend_installment_plan.html', context)


# ==================== PAYMENT SCHEDULE VIEWS ====================

@login_required
def payment_schedule_list(request):
    """
    Display list of payment schedules
    """
    schedules = PaymentSchedule.objects.select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle',
        'payment'
    ).order_by('due_date')
    
    # Filtering
    status_filter = request.GET.get('status')
    
    if status_filter == 'pending':
        schedules = schedules.filter(is_paid=False)
    elif status_filter == 'paid':
        schedules = schedules.filter(is_paid=True)
    elif status_filter == 'overdue':
        schedules = schedules.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        )
    elif status_filter == 'due_this_month':
        now = timezone.now()
        schedules = schedules.filter(
            is_paid=False,
            due_date__year=now.year,
            due_date__month=now.month
        )
    
    # Statistics
    total_schedules = schedules.count()
    pending_schedules = PaymentSchedule.objects.filter(is_paid=False).count()
    paid_schedules = PaymentSchedule.objects.filter(is_paid=True).count()
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    # Pagination
    paginator = Paginator(schedules, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'schedules': page_obj,
        'total_schedules': total_schedules,
        'pending_schedules': pending_schedules,
        'paid_schedules': paid_schedules,
        'overdue_schedules': overdue_schedules,
    }
    
    log_audit(request.user, 'view', 'PaymentSchedule', 'Viewed payment schedule list')
    
    return render(request, 'payments/payment_schedule_list.html', context)


@login_required
def overdue_payments(request):
    """
    Display overdue payment schedules
    """
    today = timezone.now().date()
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    ).order_by('due_date')

    # Optional filters from UI
    search = request.GET.get('search', '').strip()
    if search:
        overdue_schedules = overdue_schedules.filter(
            Q(installment_plan__client_vehicle__client__first_name__icontains=search) |
            Q(installment_plan__client_vehicle__client__last_name__icontains=search) |
            Q(installment_plan__client_vehicle__vehicle__registration_number__icontains=search) |
            Q(installment_plan__client_vehicle__vehicle__vin__icontains=search)
        )

    days_overdue_filter = request.GET.get('days_overdue', '').strip()
    if days_overdue_filter.isdigit():
        min_days = int(days_overdue_filter)
        cutoff_date = today - timedelta(days=min_days)
        overdue_schedules = overdue_schedules.filter(due_date__lte=cutoff_date)
    
    # Calculate totals
    total_overdue_amount = overdue_schedules.aggregate(
        total=Sum(F('amount_due') - F('amount_paid'))
    )['total'] or 0
    total_late_fees = overdue_schedules.aggregate(
        total=Sum('late_fee_applied')
    )['total'] or 0
    total_overdue_with_fees = total_overdue_amount + total_late_fees

    total_overdue_count = overdue_schedules.count()
    affected_clients_count = overdue_schedules.values(
        'installment_plan__client_vehicle__client'
    ).distinct().count()

    if total_overdue_count:
        total_days_overdue = sum(schedule.days_overdue for schedule in overdue_schedules)
        average_days_overdue = total_days_overdue / total_overdue_count
    else:
        average_days_overdue = 0

    paginator = Paginator(overdue_schedules, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for schedule in page_obj:
        schedule.total_due_with_late_fee = schedule.remaining_amount + (schedule.late_fee_applied or 0)
    
    context = {
        'overdue_schedules': page_obj,
        'total_overdue_amount': total_overdue_amount,
        'total_late_fees': total_late_fees,
        'total_overdue_with_fees': total_overdue_with_fees,
        'total_overdue_count': total_overdue_count,
        'total_count': total_overdue_count,
        'affected_clients_count': affected_clients_count,
        'average_days_overdue': average_days_overdue,
    }
    
    log_audit(request.user, 'view', 'PaymentSchedule', 'Viewed overdue payments')
    
    return render(request, 'payments/overdue_payments.html', context)


# ==================== REPORTING VIEWS ====================

@login_required
def payment_tracker(request, client_vehicle_pk):
    """
    Display payment tracker for a specific client vehicle
    """
    from django.utils import timezone
    from django.db.models import Sum, Count
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    now = timezone.now()
    today = now.date()
    
    # Get all payments
    payments = Payment.objects.filter(
        client_vehicle=client_vehicle
    ).order_by('payment_date')
    
    # Get installment plan if exists
    try:
        plan = client_vehicle.installment_plan
        schedules = plan.payment_schedules.all().order_by('installment_number')
    except InstallmentPlan.DoesNotExist:
        plan = None
        schedules = None
    
    # Calculate statistics for this client vehicle
    today_payments = payments.filter(payment_date=today)
    today_collections = today_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    today_payment_count = today_payments.count()
    
    # This week (last 7 days)
    week_start = today - timezone.timedelta(days=7)
    week_payments = payments.filter(payment_date__gte=week_start)
    week_collections = week_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    week_payment_count = week_payments.count()
    
    # This month
    month_payments = payments.filter(
        payment_date__year=now.year,
        payment_date__month=now.month
    )
    month_collections = month_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    month_payment_count = month_payments.count()
    
    # Expected today (due payments today - past/current due dates only)
    if schedules:
        due_today_schedules = schedules.filter(
            is_paid=False,
            due_date=today
        )
        expected_today = due_today_schedules.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        due_today_count = due_today_schedules.count()
        
        # Due this week (due dates from today to end of week)
        week_end = today + timezone.timedelta(days=7)
        due_week_schedules = schedules.filter(
            is_paid=False,
            due_date__gte=today,
            due_date__lte=week_end
        )
        due_week_count = due_week_schedules.count()
    else:
        expected_today = 0
        due_today_count = 0
        due_week_count = 0
    
    context = {
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
        'payments': payments,
        'plan': plan,
        'schedules': schedules,
        # Statistics
        'today_collections': today_collections,
        'today_payment_count': today_payment_count,
        'week_collections': week_collections,
        'week_payment_count': week_payment_count,
        'month_collections': month_collections,
        'month_payment_count': month_payment_count,
        'expected_today': expected_today,
        'due_today_count': due_today_count,
        'due_week_count': due_week_count,
    }
    
    log_audit(
        request.user, 'view', 'Payment',
        f'Viewed payment tracker for {client_vehicle.client.get_full_name()}'
    )
    
    return render(request, 'payments/payment_tracker.html', context)


@login_required
def payment_analytics(request):
    """
    Display payment analytics and statistics
    """
    now = timezone.now()
    today = now.date()

    try:
        period_days = int(request.GET.get('period', '30'))
        if period_days <= 0:
            period_days = 30
    except (TypeError, ValueError):
        period_days = 30

    start_date = today - timedelta(days=period_days - 1)
    previous_start = start_date - timedelta(days=period_days)
    previous_end = start_date - timedelta(days=1)

    period_payments = Payment.objects.filter(payment_date__gte=start_date, payment_date__lte=today)
    previous_period_payments = Payment.objects.filter(payment_date__gte=previous_start, payment_date__lte=previous_end)

    total_revenue = period_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_transactions = period_payments.count()
    average_payment = period_payments.aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')

    previous_revenue = previous_period_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    previous_transactions = previous_period_payments.count()

    if previous_revenue > 0:
        revenue_growth = ((total_revenue - previous_revenue) / previous_revenue) * 100
    elif total_revenue > 0:
        revenue_growth = Decimal('100.00')
    else:
        revenue_growth = Decimal('0.00')

    if previous_transactions > 0:
        transaction_growth = ((total_transactions - previous_transactions) / previous_transactions) * 100
    elif total_transactions > 0:
        transaction_growth = Decimal('100.00')
    else:
        transaction_growth = Decimal('0.00')

    expected_schedules = PaymentSchedule.objects.filter(due_date__gte=start_date, due_date__lte=today)
    expected_total = expected_schedules.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    collection_rate = ((total_revenue / expected_total) * 100) if expected_total > 0 else Decimal('0.00')

    method_rows = period_payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    method_map = dict(Payment.PAYMENT_METHOD_CHOICES)
    payment_methods_stats = []
    for row in method_rows:
        method_total = row['total'] or Decimal('0.00')
        pct = ((method_total / total_revenue) * 100) if total_revenue > 0 else Decimal('0.00')
        payment_methods_stats.append({
            'name': method_map.get(row['payment_method'], row['payment_method'] or 'Unknown').title(),
            'total': method_total,
            'count': row['count'],
            'percentage': pct,
        })

    top_clients_rows = period_payments.values(
        'client_vehicle__client__first_name',
        'client_vehicle__client__last_name'
    ).annotate(
        total_paid=Sum('amount'),
        transaction_count=Count('id')
    ).order_by('-total_paid')[:5]
    top_clients = []
    for row in top_clients_rows:
        first_name = row.get('client_vehicle__client__first_name') or ''
        last_name = row.get('client_vehicle__client__last_name') or ''
        full_name = (f"{first_name} {last_name}").strip() or 'Unknown Client'
        top_clients.append({
            'name': full_name,
            'total_paid': row['total_paid'] or Decimal('0.00'),
            'transaction_count': row['transaction_count'],
        })

    on_time_count = PaymentSchedule.objects.filter(
        is_paid=True,
        due_date__gte=start_date,
        due_date__lte=today,
        payment_date__isnull=False,
        payment_date__lte=F('due_date')
    ).count()
    late_count = PaymentSchedule.objects.filter(
        is_paid=True,
        due_date__gte=start_date,
        due_date__lte=today,
        payment_date__isnull=False,
        payment_date__gt=F('due_date')
    ).count()
    overdue_count = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__gte=start_date,
        due_date__lte=today,
        due_date__lt=today
    ).count()

    status_total = on_time_count + late_count + overdue_count
    on_time_percentage = (on_time_count / status_total * 100) if status_total else 0
    late_percentage = (late_count / status_total * 100) if status_total else 0
    overdue_percentage = (overdue_count / status_total * 100) if status_total else 0

    monthly_rows = Payment.objects.filter(
        payment_date__gte=(today - timedelta(days=180))
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('month')
    max_month_total = max((row['total'] or Decimal('0.00') for row in monthly_rows), default=Decimal('0.00'))
    monthly_comparison = []
    for row in monthly_rows:
        total = row['total'] or Decimal('0.00')
        pct = ((total / max_month_total) * 100) if max_month_total > 0 else Decimal('0.00')
        month_date = row['month']
        monthly_comparison.append({
            'month_name': month_date.strftime('%b %Y') if month_date else 'Unknown',
            'total': total,
            'count': row['count'],
            'percentage': pct,
        })

    daily_rows = period_payments.values('payment_date').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('payment_date')
    daily_map = {row['payment_date']: row for row in daily_rows}
    trend_data = []
    max_daily_total = max((row['total'] or Decimal('0.00') for row in daily_rows), default=Decimal('0.00'))
    for i in range(period_days):
        day = start_date + timedelta(days=i)
        row = daily_map.get(day)
        day_total = (row['total'] if row else Decimal('0.00')) or Decimal('0.00')
        bar_width = ((day_total / max_daily_total) * 100) if max_daily_total > 0 else Decimal('0.00')
        trend_data.append({
            'label': day.strftime('%d %b'),
            'total': day_total,
            'count': row['count'] if row else 0,
            'bar_width': bar_width,
        })

    recent_payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle'
    ).order_by('-payment_date', '-created_at')[:10]

    context = {
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'average_payment': average_payment,
        'collection_rate': collection_rate,
        'revenue_growth': revenue_growth,
        'transaction_growth': transaction_growth,
        'payment_methods_stats': payment_methods_stats,
        'top_clients': top_clients,
        'on_time_count': on_time_count,
        'late_count': late_count,
        'overdue_count': overdue_count,
        'on_time_percentage': on_time_percentage,
        'late_percentage': late_percentage,
        'overdue_percentage': overdue_percentage,
        'monthly_comparison': monthly_comparison,
        'trend_data': trend_data,
        'recent_payments': recent_payments,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed payment analytics')
    
    return render(request, 'payments/payment_analytics.html', context)


@login_required
def paybill_tracker(request):
    """Display paybill account balance and incoming transaction history."""
    transactions = PaybillTransaction.objects.all().order_by('-trans_time', '-created_at')
    latest_snapshot = PaybillBalanceSnapshot.objects.first()
    latest_successful_snapshot = PaybillBalanceSnapshot.objects.filter(
        status=PaybillBalanceSnapshot.STATUS_SUCCESS
    ).first()

    total_received = transactions.aggregate(Sum('trans_amount'))['trans_amount__sum'] or Decimal('0.00')
    this_month = timezone.now()
    month_received = transactions.filter(
        trans_time__year=this_month.year,
        trans_time__month=this_month.month,
    ).aggregate(Sum('trans_amount'))['trans_amount__sum'] or Decimal('0.00')

    context = {
        'transactions': transactions[:100],
        'transactions_count': transactions.count(),
        'total_received': total_received,
        'month_received': month_received,
        'latest_snapshot': latest_snapshot,
        'latest_successful_snapshot': latest_successful_snapshot,
        'daraja_configured': mpesa_is_configured(),
        'missing_mpesa_vars': get_missing_mpesa_vars(),
    }

    log_audit(request.user, 'view', 'Payment', 'Viewed paybill tracker')
    return render(request, 'payments/paybill_tracker.html', context)


@login_required
@require_POST
def refresh_paybill_balance(request):
    """Initiate an asynchronous Daraja account balance request."""
    result = request_account_balance()

    if result.get('ok'):
        response_payload = result.get('response', {})
        PaybillBalanceSnapshot.objects.create(
            status=PaybillBalanceSnapshot.STATUS_PENDING,
            request_reference=result.get('request_reference', ''),
            conversation_id=response_payload.get('ConversationID', ''),
            originator_conversation_id=response_payload.get('OriginatorConversationID', ''),
            result_code=response_payload.get('ResponseCode') if str(response_payload.get('ResponseCode', '')).isdigit() else None,
            result_desc=response_payload.get('ResponseDescription', ''),
            raw_payload=response_payload,
        )
        messages.success(request, 'Balance request sent to Daraja. Awaiting callback result.')
    else:
        missing_vars = result.get('missing_vars', [])
        if missing_vars:
            messages.error(request, f"Missing M-Pesa settings in .env: {', '.join(missing_vars)}")
        else:
            messages.error(request, f"Unable to request paybill balance: {result.get('error', 'Unknown error')}")

    return redirect('payments:paybill_tracker')


def _safe_decimal(value):
    if value is None:
        return None
    text = str(value).strip().replace(',', '')
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _parse_mpesa_datetime(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ('%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_account_balance(raw_value):
    """Extract a numeric balance from Daraja AccountBalance string payload."""
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float, Decimal)):
        return Decimal(str(raw_value))

    text = str(raw_value)
    match = re.search(r'(\d+[\d,]*\.?\d*)', text)
    if not match:
        return None
    return _safe_decimal(match.group(1))


def _normalize_account_reference(value):
    """Normalize account references to compare vehicle registration numbers reliably."""
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())


def _find_client_vehicle_for_reference(account_reference):
    if not account_reference:
        return None

    normalized = _normalize_account_reference(account_reference)
    if not normalized:
        return None

    direct_match = ClientVehicle.objects.select_related('vehicle').filter(
        is_active=True,
        vehicle__registration_number__iexact=str(account_reference).strip(),
    ).first()
    if direct_match:
        return direct_match

    for item in ClientVehicle.objects.select_related('vehicle').filter(
        is_active=True,
        vehicle__registration_number__isnull=False,
    ):
        if _normalize_account_reference(item.vehicle.registration_number) == normalized:
            return item
    return None


def _parse_stk_metadata(metadata_items):
    details = {
        'amount': None,
        'mpesa_receipt_number': '',
        'transaction_date': None,
        'phone_number': '',
    }
    if not isinstance(metadata_items, list):
        return details

    for item in metadata_items:
        name = str(item.get('Name', '')).strip().lower()
        value = item.get('Value')
        if name == 'amount':
            details['amount'] = _safe_decimal(value)
        elif name == 'mpesareceiptnumber':
            details['mpesa_receipt_number'] = str(value or '').strip()
        elif name == 'transactiondate':
            details['transaction_date'] = _parse_mpesa_datetime(value)
        elif name == 'phonenumber':
            details['phone_number'] = str(value or '').strip()

    return details


def _callback_secret_is_valid(request):
    expected_secret = str(getattr(settings, 'MPESA_CALLBACK_SECRET', '') or '').strip()
    if not expected_secret:
        return True

    provided_secret = (
        request.headers.get('X-Callback-Secret')
        or request.META.get('HTTP_X_CALLBACK_SECRET', '')
    ).strip()
    return provided_secret == expected_secret


@csrf_exempt
@require_POST
def paybill_validation_callback(request):
    """Daraja C2B validation callback endpoint."""
    if not _callback_secret_is_valid(request):
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def paybill_confirmation_callback(request):
    """Daraja C2B confirmation callback endpoint."""
    if not _callback_secret_is_valid(request):
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)

    trans_id = (payload.get('TransID') or '').strip()
    if not trans_id:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing TransID'}, status=400)

    bill_ref_number = str(payload.get('BillRefNumber', '')).strip()
    trans_amount = _safe_decimal(payload.get('TransAmount')) or Decimal('0.00')
    transaction_obj, _ = PaybillTransaction.objects.update_or_create(
        trans_id=trans_id,
        defaults={
            'trans_time': _parse_mpesa_datetime(payload.get('TransTime')),
            'trans_amount': trans_amount,
            'business_short_code': str(payload.get('BusinessShortCode', '')).strip(),
            'bill_ref_number': bill_ref_number,
            'invoice_number': str(payload.get('InvoiceNumber', '')).strip(),
            'org_account_balance': _safe_decimal(payload.get('OrgAccountBalance')),
            'msisdn': str(payload.get('MSISDN', '')).strip(),
            'first_name': str(payload.get('FirstName', '')).strip(),
            'middle_name': str(payload.get('MiddleName', '')).strip(),
            'last_name': str(payload.get('LastName', '')).strip(),
            'raw_payload': payload,
        },
    )

    client_vehicle = _find_client_vehicle_for_reference(bill_ref_number)
    if client_vehicle and not Payment.objects.filter(
        client_vehicle=client_vehicle,
        transaction_reference=trans_id,
        payment_method='mpesa',
    ).exists():
        Payment.objects.create(
            client_vehicle=client_vehicle,
            amount=trans_amount,
            payment_date=(_parse_mpesa_datetime(payload.get('TransTime')) or timezone.now()).date(),
            payment_method='mpesa',
            transaction_reference=trans_id,
            notes=f'Paybill payment received. Account ref: {bill_ref_number or "N/A"}.',
        )
        transaction_obj.is_linked_to_payment = True
        transaction_obj.save(update_fields=['is_linked_to_payment', 'updated_at'])

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def stk_push_callback(request):
    """Daraja STK push callback endpoint."""
    if not _callback_secret_is_valid(request):
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)

    callback = payload.get('Body', {}).get('stkCallback', {})
    merchant_request_id = str(callback.get('MerchantRequestID', '')).strip()
    checkout_request_id = str(callback.get('CheckoutRequestID', '')).strip()
    result_code_raw = callback.get('ResultCode')
    result_code = int(result_code_raw) if str(result_code_raw).lstrip('-').isdigit() else None
    result_desc = str(callback.get('ResultDesc', '')).strip()

    metadata = callback.get('CallbackMetadata', {}).get('Item', [])
    parsed_metadata = _parse_stk_metadata(metadata)

    stk_request = MpesaSTKRequest.objects.filter(
        checkout_request_id=checkout_request_id
    ).order_by('-created_at').first()
    if not stk_request and merchant_request_id:
        stk_request = MpesaSTKRequest.objects.filter(
            merchant_request_id=merchant_request_id
        ).order_by('-created_at').first()

    if not stk_request:
        stk_request = MpesaSTKRequest.objects.create(
            account_reference='',
            payment_type='',
            phone_number=parsed_metadata['phone_number'],
            amount=parsed_metadata['amount'] or Decimal('0.00'),
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            status=MpesaSTKRequest.STATUS_FAILED,
            result_code=result_code,
            result_desc=result_desc,
            mpesa_receipt_number=parsed_metadata['mpesa_receipt_number'],
            transaction_date=parsed_metadata['transaction_date'],
            raw_callback_payload=payload,
        )

    status = MpesaSTKRequest.STATUS_FAILED
    if result_code == 0:
        status = MpesaSTKRequest.STATUS_SUCCESS
    elif result_code in {1032, 1}:
        status = MpesaSTKRequest.STATUS_CANCELLED
    elif result_code == 1037:
        status = MpesaSTKRequest.STATUS_TIMEOUT

    stk_request.status = status
    stk_request.result_code = result_code
    stk_request.result_desc = result_desc
    stk_request.raw_callback_payload = payload
    if parsed_metadata['amount'] is not None:
        stk_request.amount = parsed_metadata['amount']
    if parsed_metadata['phone_number']:
        stk_request.phone_number = parsed_metadata['phone_number']
    if parsed_metadata['mpesa_receipt_number']:
        stk_request.mpesa_receipt_number = parsed_metadata['mpesa_receipt_number']
    if parsed_metadata['transaction_date']:
        stk_request.transaction_date = parsed_metadata['transaction_date']

    if result_code == 0 and not stk_request.payment_id:
        account_reference = stk_request.account_reference
        client_vehicle = stk_request.client_vehicle or _find_client_vehicle_for_reference(account_reference)
        amount = parsed_metadata['amount'] or stk_request.amount
        transaction_reference = parsed_metadata['mpesa_receipt_number']
        payment_date = (parsed_metadata['transaction_date'] or timezone.now()).date()

        if client_vehicle and transaction_reference:
            existing_payment = Payment.objects.filter(
                client_vehicle=client_vehicle,
                transaction_reference=transaction_reference,
                payment_method='mpesa',
            ).first()

            if existing_payment:
                stk_request.payment = existing_payment
            else:
                notes = (
                    f'M-Pesa STK payment. Account ref: {account_reference or "N/A"}. '
                    f'Phone: {parsed_metadata["phone_number"] or stk_request.phone_number or "N/A"}.'
                )
                created_payment = Payment.objects.create(
                    client_vehicle=client_vehicle,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method='mpesa',
                    transaction_reference=transaction_reference,
                    notes=notes,
                )
                stk_request.payment = created_payment

            PaybillTransaction.objects.update_or_create(
                trans_id=transaction_reference,
                defaults={
                    'trans_time': parsed_metadata['transaction_date'] or timezone.now(),
                    'trans_amount': amount,
                    'business_short_code': str(getattr(settings, 'MPESA_SHORTCODE', '') or '').strip(),
                    'bill_ref_number': account_reference,
                    'invoice_number': stk_request.checkout_request_id,
                    'msisdn': parsed_metadata['phone_number'] or stk_request.phone_number,
                    'raw_payload': payload,
                    'is_linked_to_payment': True,
                },
            )

    stk_request.save()

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def paybill_balance_result_callback(request):
    """Daraja account-balance result callback endpoint."""
    if not _callback_secret_is_valid(request):
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)

    result = payload.get('Result', {})
    result_code = result.get('ResultCode')
    status = (
        PaybillBalanceSnapshot.STATUS_SUCCESS
        if str(result_code) == '0'
        else PaybillBalanceSnapshot.STATUS_FAILED
    )

    balance = None
    parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
    if isinstance(parameters, list):
        for item in parameters:
            if str(item.get('Key', '')).lower() in {'accountbalance', 'availablebalance'}:
                balance = _extract_account_balance(item.get('Value'))
                if balance is not None:
                    break

    PaybillBalanceSnapshot.objects.create(
        status=status,
        available_balance=balance,
        conversation_id=str(result.get('ConversationID', '')).strip(),
        originator_conversation_id=str(result.get('OriginatorConversationID', '')).strip(),
        result_code=int(result_code) if str(result_code).lstrip('-').isdigit() else None,
        result_desc=str(result.get('ResultDesc', '')).strip(),
        raw_payload=payload,
    )

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def paybill_balance_timeout_callback(request):
    """Daraja account-balance timeout callback endpoint."""
    if not _callback_secret_is_valid(request):
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = {'raw': request.body.decode('utf-8', errors='ignore')}

    result = payload.get('Result', {}) if isinstance(payload, dict) else {}

    PaybillBalanceSnapshot.objects.create(
        status=PaybillBalanceSnapshot.STATUS_TIMEOUT,
        conversation_id=str(result.get('ConversationID', '')).strip(),
        originator_conversation_id=str(result.get('OriginatorConversationID', '')).strip(),
        result_desc='Daraja callback timeout',
        raw_payload=payload if isinstance(payload, dict) else {'payload': str(payload)},
    )

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def defaulters_report(request):
    """
    Generate report of clients with overdue payments
    """
    today = timezone.now().date()

    # Get all overdue payment schedules
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    ).order_by('due_date')

    # Group overdue schedules by client and calculate dynamic metrics used by template.
    defaulters = {}
    for schedule in overdue_schedules:
        client_vehicle = schedule.installment_plan.client_vehicle
        client = client_vehicle.client

        if client.id not in defaulters:
            last_payment = Payment.objects.filter(client_vehicle=client_vehicle).order_by('-payment_date', '-created_at').first()
            defaulters[client.id] = {
                'client': client,
                'vehicle': client_vehicle.vehicle,
                'client_vehicle_id': client_vehicle.id,
                'days_overdue': schedule.days_overdue,
                'overdue_installments': 0,
                'total_outstanding': Decimal('0.00'),
                'payment_percentage': Decimal('0.00'),
                'last_payment_date': last_payment.payment_date if last_payment else None,
                'last_payment_amount': last_payment.amount if last_payment else None,
            }

        defaulters[client.id]['overdue_installments'] += 1

        if schedule.days_overdue > defaulters[client.id]['days_overdue']:
            defaulters[client.id]['days_overdue'] = schedule.days_overdue

    # Compute total_outstanding and payment_percentage from ALL client vehicles (not just overdue ones).
    # Use Sum('balance') — the same authoritative stored field used by the client detail page.
    for client_id, data in defaulters.items():
        cv_totals = ClientVehicle.objects.filter(client=data['client']).aggregate(
            total_balance=Sum('balance'),
            total_purchase=Sum('purchase_price'),
            total_paid_sum=Sum('total_paid'),
        )
        total_balance = cv_totals['total_balance'] or Decimal('0.00')
        total_purchase = cv_totals['total_purchase'] or Decimal('0.00')
        total_paid = cv_totals['total_paid_sum'] or Decimal('0.00')
        data['total_outstanding'] = max(Decimal('0.00'), total_balance)
        if total_purchase > 0:
            data['payment_percentage'] = (total_paid / total_purchase) * Decimal('100')

    defaulters_list = list(defaulters.values())
    total_outstanding = sum((d['total_outstanding'] for d in defaulters_list), Decimal('0.00'))

    critical_defaulters = [d for d in defaulters_list if d['days_overdue'] >= 90]
    severe_defaulters = [d for d in defaulters_list if 60 <= d['days_overdue'] < 90]
    moderate_defaulters = [d for d in defaulters_list if 30 <= d['days_overdue'] < 60]

    critical_amount = sum((d['total_outstanding'] for d in critical_defaulters), Decimal('0.00'))
    severe_amount = sum((d['total_outstanding'] for d in severe_defaulters), Decimal('0.00'))
    moderate_amount = sum((d['total_outstanding'] for d in moderate_defaulters), Decimal('0.00'))

    average_days_overdue = Decimal('0.00')
    if defaulters_list:
        average_days_overdue = sum((Decimal(str(d['days_overdue'])) for d in defaulters_list), Decimal('0.00')) / Decimal(str(len(defaulters_list)))

    context = {
        'defaulters': defaulters_list,
        'total_defaulters': len(defaulters_list),
        'total_outstanding': total_outstanding,
        'total_overdue_amount': total_outstanding,
        'at_risk_vehicles': len(defaulters_list),
        'average_days_overdue': average_days_overdue,
        'critical_defaulters': critical_defaulters,
        'critical_total': critical_amount,
        'critical_count': len(critical_defaulters),
        'critical_amount': critical_amount,
        'severe_count': len(severe_defaulters),
        'severe_amount': severe_amount,
        'moderate_count': len(moderate_defaulters),
        'moderate_amount': moderate_amount,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed defaulters report')
    
    return render(request, 'payments/defaulters_report.html', context)


@login_required
def export_payments_csv(request):
    """
    Export payments to CSV
    """
    currency, fx_rate = _parse_export_currency(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="payments_{currency.lower()}_{timezone.now().strftime("%Y%m%d")}.csv"'
    )
    
    writer = csv.writer(response)
    writer.writerow([
        'Receipt Number', 'Client', 'ID Number', 'Vehicle', 
        'Payment Date', 'Amount', 'Currency', 'FX Rate (from KES)',
        'Payment Method', 'Transaction Reference', 'Balance', 'Recorded By'
    ])
    
    payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'recorded_by'
    ).order_by('-payment_date')
    
    # Apply filters if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    for payment in payments:
        converted_amount = _convert_kes_amount(payment.amount, fx_rate)
        converted_balance = _convert_kes_amount(payment.client_vehicle.balance, fx_rate)
        writer.writerow([
            payment.receipt_number,
            payment.client_vehicle.client.get_full_name(),
            payment.client_vehicle.client.id_number,
            str(payment.client_vehicle.vehicle),
            payment.payment_date.strftime('%Y-%m-%d'),
            converted_amount,
            currency,
            fx_rate,
            payment.get_payment_method_display(),
            payment.transaction_reference or '',
            converted_balance,
            payment.recorded_by.get_full_name() if payment.recorded_by else ''
        ])
    
    log_audit(
        request.user,
        'export',
        'Payment',
        f'Exported payments to CSV in {currency} (rate={fx_rate})'
    )
    
    return response


# ==================== AJAX/API VIEWS ====================

@login_required
def payment_stats_api(request):
    """
    API endpoint for payment statistics
    """
    now = timezone.now()
    
    # Get date range from request
    period = request.GET.get('period', 'month')  # month, year, all
    
    if period == 'month':
        payments = Payment.objects.filter(
            payment_date__year=now.year,
            payment_date__month=now.month
        )
    elif period == 'year':
        payments = Payment.objects.filter(payment_date__year=now.year)
    else:
        payments = Payment.objects.all()
    
    total = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    count = payments.count()
    
    data = {
        'total': float(total),
        'count': count,
        'average': float(total / count) if count > 0 else 0
    }
    
    return JsonResponse(data)


@login_required
def due_monitor_api(request):
    """API endpoint for near real-time due-date and defaulter counters."""
    stats = _build_due_monitor_stats()
    return JsonResponse({
        'due_today_count': stats['due_today_count'],
        'due_today_amount': float(stats['due_today_amount']),
        'overdue_count': stats['overdue_count'],
        'overdue_amount': float(stats['overdue_amount']),
        'defaulters_count': stats['defaulters_count'],
        'snapshot_time': stats['snapshot_time'].isoformat(),
    })


@login_required
def payment_chart_data_api(request):
    """
    API endpoint for payment chart data
    """
    now = timezone.now()
    
    # Get monthly data for the current year
    monthly_data = []
    for month in range(1, 13):
        total = Payment.objects.filter(
            payment_date__year=now.year,
            payment_date__month=month
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        monthly_data.append({
            'month': month,
            'total': float(total)
        })
    
    return JsonResponse({'data': monthly_data})


# ==================== PDF GENERATION VIEWS ====================

@login_required
def generate_agreement_pdf_view(request, client_vehicle_pk):
    """
    Generate and download sales agreement PDF
    """
    from .utils import generate_agreement_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    currency, fx_rate = _parse_export_currency(request)
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated agreement PDF for {client_vehicle.client.get_full_name()} in {currency}'
    )
    
    return generate_agreement_pdf(client_vehicle, currency=currency, fx_rate=fx_rate)


@login_required
def generate_proforma_invoice_pdf_view(request, client_vehicle_pk):
    """
    Generate and download proforma invoice PDF
    """
    from .utils import generate_performa_invoice_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    currency, fx_rate = _parse_export_currency(request)
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated proforma invoice for {client_vehicle.client.get_full_name()} in {currency}'
    )
    
    return generate_performa_invoice_pdf(client_vehicle, currency=currency, fx_rate=fx_rate)


@login_required
def generate_payment_tracker_pdf_view(request, client_vehicle_pk):
    """
    Generate and download payment tracker PDF
    """
    from .utils import generate_payment_tracker_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    currency, fx_rate = _parse_export_currency(request)
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated payment tracker PDF for {client_vehicle.client.get_full_name()} in {currency}'
    )
    
    return generate_payment_tracker_pdf(client_vehicle, currency=currency, fx_rate=fx_rate)


# ==================== HELPER FUNCTIONS ====================

def update_payment_schedules(payment, client_vehicle):
    """
    Update payment schedules when a payment is made
    """
    try:
        plan = client_vehicle.installment_plan
        pending_schedules = plan.payment_schedules.filter(
            is_paid=False
        ).order_by('installment_number')
        
        remaining_amount = payment.amount
        
        for schedule in pending_schedules:
            if remaining_amount <= 0:
                break
            
            amount_to_apply = min(remaining_amount, schedule.remaining_amount)
            schedule.mark_as_paid(payment, amount_to_apply)
            remaining_amount -= amount_to_apply
        
    except InstallmentPlan.DoesNotExist:
        pass


# ==================== STAFF STK PUSH AJAX ENDPOINTS ====================

@login_required
@require_POST
def staff_stk_initiate(request, client_vehicle_pk):
    """
    Initiate an M-Pesa STK Push for a staff-recorded payment.
    POST body (JSON): { phone_number, amount }
    Returns JSON: { ok, checkout_request_id, error }
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=client_vehicle_pk)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON body.'}, status=400)

    phone_raw = (body.get('phone_number') or '').strip()
    amount_raw = body.get('amount')

    # Normalise phone
    try:
        phone = _normalize_phone_number(phone_raw)
    except Exception:
        phone = None
    if not phone:
        return JsonResponse({
            'ok': False,
            'error': 'Enter a valid Kenyan phone number '
                     '(e.g. 0712345678, 254712345678).'
        }, status=400)

    # Normalise amount
    try:
        amount = Decimal(str(amount_raw).replace(',', ''))
        if amount <= 0:
            raise ValueError
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid amount.'}, status=400)

    account_reference = client_vehicle.vehicle.registration_number or f'VEH{client_vehicle.pk}'
    transaction_desc = (
        f'Payment for {account_reference} by {client_vehicle.client.get_full_name()}'
    )[:100]

    result = initiate_stk_push(
        phone_number=phone,
        amount=amount,
        account_reference=account_reference,
        transaction_desc=transaction_desc,
    )

    if not result.get('ok'):
        return JsonResponse({'ok': False, 'error': result.get('error', 'STK push failed.')})

    response_data = result.get('response', {})
    checkout_request_id = response_data.get('CheckoutRequestID', '')
    merchant_request_id = response_data.get('MerchantRequestID', '')

    stk_req = MpesaSTKRequest.objects.create(
        client_vehicle=client_vehicle,
        account_reference=account_reference,
        payment_type='installment',
        phone_number=phone,
        amount=amount,
        merchant_request_id=merchant_request_id,
        checkout_request_id=checkout_request_id,
        response_code=response_data.get('ResponseCode', ''),
        response_description=response_data.get('ResponseDescription', ''),
        status='pending',
        raw_request_payload=result.get('request_payload', {}),
        raw_response_payload=response_data,
    )

    log_audit(
        request.user, 'create', 'MpesaSTKRequest',
        f'Staff STK push initiated: {account_reference}, KES {amount}, phone {phone}'
    )

    return JsonResponse({
        'ok': True,
        'checkout_request_id': stk_req.checkout_request_id,
    })


@login_required
def staff_stk_status(request):
    """
    Poll the status of a staff-initiated STK push.
    GET ?checkout_request_id=<id>
    Returns JSON: { ok, status, paid, mpesa_receipt_number, result_desc }
    """
    checkout_request_id = request.GET.get('checkout_request_id', '').strip()
    if not checkout_request_id:
        return JsonResponse({'ok': False, 'error': 'checkout_request_id required.'}, status=400)
    try:
        stk_req = MpesaSTKRequest.objects.get(checkout_request_id=checkout_request_id)
    except MpesaSTKRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Request not found.'}, status=404)

    return JsonResponse({
        'ok': True,
        'status': stk_req.status,
        'paid': stk_req.status == 'success',
        'mpesa_receipt_number': stk_req.mpesa_receipt_number or '',
        'result_desc': stk_req.result_desc or '',
    })