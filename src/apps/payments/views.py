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
import logging

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
    initiate_stk_push, _normalize_phone_number, register_c2b_urls,
)
from apps.clients.models import Client, ClientVehicle
from apps.audit.utils import log_audit
from utils.decorators import module_permission_required
from utils.constants import AccessLevel

# Initialize logger
logger = logging.getLogger(__name__)


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

    due_today_qs = PaymentSchedule.objects.filter(is_paid=False, due_date=today, installment_plan__is_active=True)
    overdue_qs = PaymentSchedule.objects.filter(is_paid=False, due_date__lt=today, installment_plan__is_active=True)

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


def _safe_decimal(value):
    """Safely convert a value to Decimal."""
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
    """Parse M-Pesa datetime string to datetime object."""
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
    """
    Extract a numeric balance from Daraja AccountBalance string payload.
    Handles the complex format: "Account|KES|balance|...|..."
    Example: "Utility Account|KES|200153.00|200153.00|0.00|0.00"
    """
    if raw_value is None:
        logger.warning("_extract_account_balance: raw_value is None")
        return None
    
    if isinstance(raw_value, (int, float, Decimal)):
        logger.info(f"_extract_account_balance: Got numeric value: {raw_value}")
        return Decimal(str(raw_value))
    
    if isinstance(raw_value, str):
        logger.info(f"_extract_account_balance: Processing string: {raw_value[:200]}...")
        
        # Look for Utility Account specifically (this has the actual balance)
        if 'Utility Account' in raw_value:
            import re
            # Pattern: Utility Account|KES|123.45|...
            match = re.search(r'Utility Account\s*\|\s*KES\s*\|\s*([\d,]+\.?\d*)', raw_value)
            if match:
                try:
                    balance = Decimal(match.group(1).replace(',', ''))
                    logger.info(f"✅ Found Utility Account balance: {balance}")
                    return balance
                except (ValueError, InvalidOperation):
                    pass
        
        # If no Utility Account, try Working Account
        if 'Working Account' in raw_value:
            import re
            match = re.search(r'Working Account\s*\|\s*KES\s*\|\s*([\d,]+\.?\d*)', raw_value)
            if match:
                try:
                    balance = Decimal(match.group(1).replace(',', ''))
                    logger.info(f"✅ Found Working Account balance: {balance}")
                    return balance
                except (ValueError, InvalidOperation):
                    pass
        
        # Fallback: find any balance in the string
        import re
        matches = re.findall(r'KES\s*\|\s*([\d,]+\.?\d*)', raw_value)
        for match in matches:
            try:
                balance = Decimal(match.replace(',', ''))
                if balance > 0:
                    logger.info(f"✅ Found balance via fallback: {balance}")
                    return balance
            except (ValueError, InvalidOperation):
                continue
        
        # One more fallback: find any decimal number in the string
        matches = re.findall(r'(\d+[\d,]*\.?\d*)', raw_value)
        if matches:
            for match in matches:
                try:
                    balance = Decimal(match.replace(',', ''))
                    if balance > 0:
                        logger.info(f"✅ Found balance via final fallback: {balance}")
                        return balance
                except (ValueError, InvalidOperation):
                    continue
        
        logger.warning(f"Could not extract balance from: {raw_value[:100]}...")
        return None
    
    logger.warning(f"_extract_account_balance: Unhandled type: {type(raw_value)}")
    return None


def _normalize_account_reference(value):
    """Normalize account references to compare vehicle registration numbers reliably."""
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())


def _find_client_vehicle_for_reference(account_reference):
    """Find a ClientVehicle by account reference (car registration)."""
    if not account_reference:
        return None

    normalized = _normalize_account_reference(account_reference)
    if not normalized:
        return None

    # Direct match
    direct_match = ClientVehicle.objects.select_related('vehicle', 'client').filter(
        is_active=True,
        vehicle__registration_number__iexact=str(account_reference).strip(),
    ).first()
    if direct_match:
        return direct_match

    # Normalized match
    for item in ClientVehicle.objects.select_related('vehicle', 'client').filter(
        is_active=True,
        vehicle__registration_number__isnull=False,
    ):
        if _normalize_account_reference(item.vehicle.registration_number) == normalized:
            return item
    return None


def _parse_stk_metadata(metadata_items):
    """Parse STK callback metadata."""
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
    """Validate the callback secret header."""
    expected_secret = str(getattr(settings, 'MPESA_CALLBACK_SECRET', '') or '').strip()
    
    # In development, allow if no secret is set
    if not expected_secret and getattr(settings, 'MPESA_ENV', '') != 'production':
        return True
    
    provided_secret = (
        request.headers.get('X-Callback-Secret')
        or request.META.get('HTTP_X_CALLBACK_SECRET', '')
    ).strip()
    
    # If both are empty, allow (development only)
    if not expected_secret and not provided_secret:
        return True
    
    # If one is set but doesn't match, reject
    return provided_secret == expected_secret


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
    
    # Statistics (active, non-reversed payments only)
    active_payments = payments.filter(is_reversed=False)
    total_payments = active_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    payment_count = active_payments.count()

    # This month statistics
    now = timezone.now()
    this_month_payments = Payment.objects.filter(
        payment_date__year=now.year,
        payment_date__month=now.month,
        is_reversed=False,
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    hoza_methods = {'equity_hoza', 'dib_hoza', 'coop_hoza'}

    hoza_total = Decimal('0.00')
    ke_total = Decimal('0.00')
    cash_total = Decimal('0.00')
    other_total = Decimal('0.00')

    hoza_breakdown = {'equity_hoza': Decimal('0.00'), 'dib_hoza': Decimal('0.00'), 'coop_hoza': Decimal('0.00')}
    ke_breakdown = {'kcb_ke': Decimal('0.00'), 'absa_ke': Decimal('0.00'), 'equity_ke': Decimal('0.00')}

    for payment in active_payments:
        if payment.splits.exists():
            portions = [(split.payment_method, split.amount) for split in payment.splits.all()]
        else:
            portions = [(payment.payment_method, payment.amount)]

        for method, amount in portions:
            method_value = (method or '').lower()
            amt = amount or Decimal('0.00')
            if method_value in hoza_methods:
                hoza_total += amt
                hoza_breakdown[method_value] = hoza_breakdown.get(method_value, Decimal('0.00')) + amt
            elif method_value.endswith('_ke'):
                ke_total += amt
                ke_breakdown[method_value] = ke_breakdown.get(method_value, Decimal('0.00')) + amt
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
        'hoza_breakdown': hoza_breakdown,
        'ke_breakdown': ke_breakdown,
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
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def reverse_payment(request, pk):
    """
    Reverse (void) a payment. The payment record is kept for audit purposes
    but is excluded from balances, totals, and payment schedule progress.
    """
    payment = get_object_or_404(Payment, pk=pk)
    reason = (request.POST.get('reason') or '').strip()

    try:
        payment.reverse_payment(user=request.user, reason=reason)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('payments:payment_detail', pk=pk)

    log_audit(
        request.user,
        'update',
        'Payment',
        f'Reversed payment {payment.receipt_number} (KES {payment.amount:,.2f}): {reason}'
    )
    messages.success(request, f'Payment {payment.receipt_number} has been reversed.')
    return redirect('payments:payment_detail', pk=pk)


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
                    pre_save_amounts = _snapshot_pending_schedule_amounts(client_vehicle)

                    # Create main payment with MIXED method.
                    # Payment.save() triggers payments/signals1.py, which recalculates
                    # client_vehicle.total_paid/balance/is_paid_off and marks off
                    # instalment schedules — do not duplicate that here.
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=_parse_payment_date(request.POST.get('payment_date')),
                        payment_method='mixed',
                        notes=request.POST.get('notes', ''),
                        recorded_by=request.user,
                        account_id=request.POST.get('account') or None,
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

                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
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

                    # Post to the finance ledger and link it to the instalments it settled
                    ledger_transaction = _record_finance_ledger_entry(payment, client_vehicle)
                    _allocate_ledger_transaction_to_schedules(ledger_transaction, client_vehicle, pre_save_amounts)

                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )

                    return redirect('payments:payment_detail', pk=payment.pk)

                except (ValueError, InvalidOperation) as e:
                    messages.error(request, f'Invalid split amounts: {str(e)}')
        else:
            # Single payment (traditional flow)
            form = PaymentForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    pre_save_amounts = _snapshot_pending_schedule_amounts(client_vehicle)

                    payment = form.save(commit=False)
                    payment.client_vehicle = client_vehicle
                    payment.recorded_by = request.user
                    # Payment.save() triggers payments/signals1.py, which recalculates
                    # client_vehicle.total_paid/balance/is_paid_off and marks off
                    # instalment schedules — do not duplicate that here.
                    payment.save()

                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
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

                    # Post to the finance ledger and link it to the instalments it settled
                    ledger_transaction = _record_finance_ledger_entry(payment, client_vehicle)
                    _allocate_ledger_transaction_to_schedules(ledger_transaction, client_vehicle, pre_save_amounts)

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
                    pre_save_amounts = _snapshot_pending_schedule_amounts(client_vehicle)

                    # Calculate total from splits
                    total_amount = sum(Decimal(a) for _, a, _, _ in valid_splits)

                    # Create main payment with MIXED method.
                    # Payment.save() triggers payments/signals1.py, which recalculates
                    # client_vehicle.total_paid/balance/is_paid_off and marks off
                    # instalment schedules — do not duplicate that here.
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=_parse_payment_date(request.POST.get('payment_date')),
                        payment_method='mixed',
                        notes=request.POST.get('notes', ''),
                        recorded_by=request.user,
                        account_id=request.POST.get('account') or None,
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

                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
                        messages.success(request, f'Split payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Split payment of KES {payment.amount:,.2f} recorded! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )

                    # Post to the finance ledger and link it to the instalments it settled
                    ledger_transaction = _record_finance_ledger_entry(payment, client_vehicle)
                    _allocate_ledger_transaction_to_schedules(ledger_transaction, client_vehicle, pre_save_amounts)

                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )

                    return redirect('payments:payment_detail', pk=payment.pk)

                except (ValueError, InvalidOperation, ClientVehicle.DoesNotExist) as e:
                    messages.error(request, f'Error processing split payment: {str(e)}')
        else:
            # Single payment (traditional flow)
            form = PaymentForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.recorded_by = request.user
                    # Payment.save() triggers payments/signals1.py, which recalculates
                    # client_vehicle.total_paid/balance/is_paid_off and marks off
                    # instalment schedules — do not duplicate that here.
                    payment.save()

                    client_vehicle = payment.client_vehicle
                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
                        messages.success(request, f'Payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Payment of KES {payment.amount:,.2f} recorded successfully! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )

                    # Post to the finance ledger. NOTE: this form has no
                    # pre-save snapshot of schedule amounts (client_vehicle
                    # isn't resolvable until after the ModelForm saves), so
                    # no PaymentAllocation is created for this path.
                    _record_finance_ledger_entry(payment, client_vehicle)

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
        ).prefetch_related('splits'),
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
    
    # Total overdue balance: sum of ClientVehicle.balance for each distinct vehicle
    # with at least one overdue schedule (authoritative stored balance, not installment sums).
    overdue_cv_ids = overdue_schedules.values_list(
        'installment_plan__client_vehicle__id', flat=True
    ).distinct()
    total_overdue_amount = ClientVehicle.objects.filter(
        id__in=overdue_cv_ids
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    total_late_fees = overdue_schedules.aggregate(
        total=Sum('late_fee_applied')
    )['total'] or Decimal('0.00')
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
        cv_balance = schedule.installment_plan.client_vehicle.balance or Decimal('0.00')
        schedule.balance_due = cv_balance
        schedule.total_due_with_late_fee = cv_balance + (schedule.late_fee_applied or Decimal('0.00'))
    
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
    """Display paybill account balance and incoming M-Pesa transaction history."""
    # Backfill: ensure every M-Pesa Payment that has no PaybillTransaction yet
    # gets a synthetic one so it immediately appears in the tracker.
    _backfill_paybill_transactions()

    all_transactions = PaybillTransaction.objects.all().order_by(
        F('trans_time').desc(nulls_last=True), '-created_at'
    )

    # Optional filter by paybill shortcode
    paybill_filter = request.GET.get('paybill', '').strip()
    if paybill_filter:
        transactions = all_transactions.filter(business_short_code=paybill_filter)
    else:
        transactions = all_transactions

    latest_snapshot = PaybillBalanceSnapshot.objects.first()
    latest_successful_snapshot = PaybillBalanceSnapshot.objects.filter(
        status=PaybillBalanceSnapshot.STATUS_SUCCESS
    ).first()

    this_month = timezone.now()

    total_received = transactions.aggregate(total=Sum('trans_amount'))['total'] or Decimal('0.00')
    month_received = transactions.filter(
        trans_time__year=this_month.year,
        trans_time__month=this_month.month,
    ).aggregate(total=Sum('trans_amount'))['total'] or Decimal('0.00')

    # Per-paybill breakdown
    known_paybills = ['4320049', '4162495']
    paybill_stats = []
    for code in known_paybills:
        qs = all_transactions.filter(business_short_code=code)
        paybill_stats.append({
            'code': code,
            'count': qs.count(),
            'total': qs.aggregate(total=Sum('trans_amount'))['total'] or Decimal('0.00'),
            'month': qs.filter(
                trans_time__year=this_month.year,
                trans_time__month=this_month.month,
            ).aggregate(total=Sum('trans_amount'))['total'] or Decimal('0.00'),
        })

    context = {
        'transactions': transactions[:100],
        'transactions_count': transactions.count(),
        'total_received': total_received,
        'month_received': month_received,
        'latest_snapshot': latest_snapshot,
        'latest_successful_snapshot': latest_successful_snapshot,
        'daraja_configured': mpesa_is_configured(),
        'missing_mpesa_vars': get_missing_mpesa_vars(),
        'paybill_stats': paybill_stats,
        'paybill_filter': paybill_filter,
    }

    log_audit(request.user, 'view', 'Payment', 'Viewed paybill tracker')
    return render(request, 'payments/paybill_tracker.html', context)


def _backfill_paybill_transactions():
    """
    Create a PaybillTransaction for every M-Pesa Payment that has a
    transaction_reference but no matching PaybillTransaction yet.
    Runs on each tracker page load — idempotent and fast once backfilled.
    """
    try:
        existing_ids = set(
            PaybillTransaction.objects.values_list('trans_id', flat=True)
        )
        orphan_payments = Payment.objects.filter(
            payment_method='mpesa',
            transaction_reference__isnull=False,
        ).exclude(
            transaction_reference__in=existing_ids
        ).select_related('client_vehicle__vehicle').order_by('-payment_date')[:200]

        shortcode = str(getattr(settings, 'MPESA_SHORTCODE', '') or '').strip()

        for pmt in orphan_payments:
            if not pmt.transaction_reference:
                continue
            try:
                cv = pmt.client_vehicle
                PaybillTransaction.objects.get_or_create(
                    trans_id=pmt.transaction_reference,
                    defaults={
                        'trans_time': timezone.datetime.combine(
                            pmt.payment_date, timezone.datetime.min.time(),
                            tzinfo=timezone.get_current_timezone(),
                        ),
                        'trans_amount': pmt.amount,
                        'business_short_code': shortcode,
                        'bill_ref_number': cv.vehicle.registration_number if cv and cv.vehicle else '',
                        'msisdn': '',
                        'raw_payload': {},
                        'is_linked_to_payment': True,
                    },
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Backfill skipped: {e}")


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


@login_required
@require_POST
def register_paybill_c2b(request):
    """Register C2B callback URLs with Safaricom for all configured paybills."""
    paybills = [
        {
            'shortcode': settings.MPESA_SHORTCODE,
            'consumer_key': settings.MPESA_CONSUMER_KEY,
            'consumer_secret': settings.MPESA_CONSUMER_SECRET,
        },
        {
            'shortcode': getattr(settings, 'MPESA_SHORTCODE_2', ''),
            'consumer_key': getattr(settings, 'MPESA_CONSUMER_KEY_2', ''),
            'consumer_secret': getattr(settings, 'MPESA_CONSUMER_SECRET_2', ''),
        },
    ]
    results = []
    for pb in paybills:
        if not pb['shortcode']:
            continue
        result = register_c2b_urls(
            pb['shortcode'],
            consumer_key=pb['consumer_key'],
            consumer_secret=pb['consumer_secret'],
        )
        results.append({'code': pb['shortcode'], **result})

    ok_count = sum(1 for r in results if r.get('ok'))
    fail_count = len(results) - ok_count

    if ok_count == len(results):
        messages.success(request, f'C2B URLs registered successfully for both paybills.')
    elif ok_count > 0:
        messages.warning(request, f'Registered {ok_count} paybill(s), {fail_count} failed. Check errors below.')
    else:
        errors = '; '.join(r.get('error', 'Unknown') for r in results if not r.get('ok'))
        messages.error(request, f'C2B registration failed: {errors}')

    log_audit(request.user, 'action', 'Payment', 'Triggered C2B URL registration for all paybills')
    return redirect('payments:paybill_tracker')


# ==================== MPESA CALLBACK VIEWS ====================

@csrf_exempt
@require_POST
def paybill_validation_callback(request):
    """
    Daraja C2B validation callback endpoint.
    Always accepts — rejecting here silently blocks the customer's payment and
    prevents the confirmation callback from ever arriving, so transactions are
    never recorded. Business-logic checks happen at confirmation time instead.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        # Even on bad JSON we accept so M-Pesa doesn't retry indefinitely
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    if not _callback_secret_is_valid(request):
        logger.warning("Unauthorized C2B validation attempt")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    bill_ref_number = str(payload.get('BillRefNumber', '')).strip()
    trans_amount = _safe_decimal(payload.get('TransAmount')) or Decimal('0.00')
    trans_id = str(payload.get('TransID', '')).strip()
    logger.info(
        f"C2B Validation: Ref={bill_ref_number}, Amount={trans_amount}, "
        f"TransID={trans_id} — accepted (validation is permissive)"
    )
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def paybill_confirmation_callback(request):
    """
    Daraja C2B confirmation callback endpoint.

    Always stores the PaybillTransaction so it appears in the tracker.
    The post_save signal (process_paybill_transaction in signals.py) creates
    the Payment and recalculates the vehicle balance — balance updates are NOT
    done here to avoid double-counting.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in C2B confirmation: {e}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)

    if not _callback_secret_is_valid(request):
        logger.warning("Unauthorized C2B confirmation attempt")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)

    trans_id = str(payload.get('TransID', '')).strip()
    if not trans_id:
        logger.error("Missing TransID in C2B confirmation")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing TransID'}, status=400)

    # Idempotent — acknowledge without creating a duplicate
    if PaybillTransaction.objects.filter(trans_id=trans_id).exists():
        logger.info(f"C2B duplicate {trans_id} — already stored")
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Duplicate - Already Processed'})

    bill_ref_number = str(payload.get('BillRefNumber', '')).strip()
    trans_amount = _safe_decimal(payload.get('TransAmount')) or Decimal('0.00')
    business_shortcode = str(payload.get('BusinessShortCode', '')).strip()
    msisdn = str(payload.get('MSISDN', '')).strip()
    trans_time = _parse_mpesa_datetime(payload.get('TransTime'))
    first_name = str(payload.get('FirstName', '')).strip()
    middle_name = str(payload.get('MiddleName', '')).strip()
    last_name = str(payload.get('LastName', '')).strip()

    logger.info(f"C2B Confirmation: Ref={bill_ref_number}, Amount={trans_amount}, TransID={trans_id}")

    # Store the transaction unconditionally so it always appears in the tracker.
    # The post_save signal (process_paybill_transaction in signals.py) will
    # create the Payment and recalculate the vehicle balance automatically.
    try:
        PaybillTransaction.objects.create(
            trans_id=trans_id,
            trans_time=trans_time or timezone.now(),
            trans_amount=trans_amount,
            business_short_code=business_shortcode,
            bill_ref_number=bill_ref_number,
            invoice_number=str(payload.get('InvoiceNumber', '')).strip(),
            org_account_balance=_safe_decimal(payload.get('OrgAccountBalance')),
            msisdn=msisdn,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            raw_payload=payload,
            is_linked_to_payment=False,
        )
        logger.info(f"✅ C2B PaybillTransaction {trans_id} stored — signal will handle Payment creation")
    except Exception as e:
        logger.error(f"Error storing C2B transaction {trans_id}: {e}", exc_info=True)
        # Return 200 anyway — returning ResultCode 1 causes M-Pesa to retry

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def stk_push_callback(request):
    """
    Daraja STK push callback endpoint.
    Processes STK push responses and creates payments on success.
    """
    logger.info("=" * 60)
    logger.info("STK Push Callback Received")
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in STK callback: {e}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)
    
    # ✅ Validate callback secret
    if not _callback_secret_is_valid(request):
        logger.warning("Unauthorized STK callback attempt - invalid secret")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)
    
    callback = payload.get('Body', {}).get('stkCallback', {})
    merchant_request_id = str(callback.get('MerchantRequestID', '')).strip()
    checkout_request_id = str(callback.get('CheckoutRequestID', '')).strip()
    result_code_raw = callback.get('ResultCode')
    result_code = int(result_code_raw) if str(result_code_raw).lstrip('-').isdigit() else None
    result_desc = str(callback.get('ResultDesc', '')).strip()
    
    logger.info(f"STK Details: CheckoutID={checkout_request_id}, ResultCode={result_code}, ResultDesc={result_desc}")
    
    # ✅ Parse metadata
    metadata = callback.get('CallbackMetadata', {}).get('Item', [])
    parsed_metadata = _parse_stk_metadata(metadata)
    
    logger.info(f"Parsed Metadata: {parsed_metadata}")
    
    # ✅ Find the STK request
    stk_request = MpesaSTKRequest.objects.filter(
        checkout_request_id=checkout_request_id
    ).order_by('-created_at').first()
    
    if not stk_request and merchant_request_id:
        stk_request = MpesaSTKRequest.objects.filter(
            merchant_request_id=merchant_request_id
        ).order_by('-created_at').first()
    
    if not stk_request:
        logger.warning(f"STK request not found for CheckoutID: {checkout_request_id}")
        # Create a record for tracking
        stk_request = MpesaSTKRequest.objects.create(
            account_reference='',
            payment_type='unknown',
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
    
    # ✅ Determine status
    status = MpesaSTKRequest.STATUS_FAILED
    if result_code == 0:
        status = MpesaSTKRequest.STATUS_SUCCESS
    elif result_code in {1032, 1}:
        status = MpesaSTKRequest.STATUS_CANCELLED
    elif result_code == 1037:
        status = MpesaSTKRequest.STATUS_TIMEOUT
    
    # ✅ Update STK request
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
    
    # ✅ Process successful payment
    if result_code == 0 and not stk_request.payment_id:
        account_reference = stk_request.account_reference
        client_vehicle = stk_request.client_vehicle or _find_client_vehicle_for_reference(account_reference)
        amount = parsed_metadata['amount'] or stk_request.amount
        transaction_reference = parsed_metadata['mpesa_receipt_number']
        trans_time = parsed_metadata['transaction_date'] or timezone.now()
        payment_date = trans_time.date() if hasattr(trans_time, 'date') else timezone.now().date()
        phone_number = parsed_metadata['phone_number'] or stk_request.phone_number

        # Store the transaction record first so it always appears in the tracker,
        # even if Payment creation below fails. Use checkout_request_id as fallback
        # trans_id when the M-Pesa receipt number is not yet available.
        paybill_trans_id = transaction_reference or checkout_request_id
        if paybill_trans_id and amount and amount > 0:
            try:
                PaybillTransaction.objects.update_or_create(
                    trans_id=paybill_trans_id,
                    defaults={
                        'trans_time': trans_time,
                        'trans_amount': amount,
                        'business_short_code': str(getattr(settings, 'MPESA_SHORTCODE', '') or '').strip(),
                        'bill_ref_number': account_reference,
                        'invoice_number': checkout_request_id,
                        'msisdn': phone_number,
                        'raw_payload': payload,
                        'is_linked_to_payment': False,
                    },
                )
                logger.info(f"✅ STK PaybillTransaction {paybill_trans_id} stored")
            except Exception as e:
                logger.error(f"Error storing STK PaybillTransaction {paybill_trans_id}: {e}", exc_info=True)

        # Create or link the Payment. The post_save signal on Payment handles
        # balance recalculation — do NOT update client_vehicle manually here.
        if client_vehicle and transaction_reference and amount and amount > 0:
            logger.info(f"Processing STK payment: Vehicle={account_reference}, Amount={amount}, Receipt={transaction_reference}")
            try:
                existing_payment = Payment.objects.filter(
                    transaction_reference=transaction_reference,
                    payment_method='mpesa',
                ).first()

                if existing_payment:
                    stk_request.payment = existing_payment
                    logger.info(f"STK payment already exists: {existing_payment.receipt_number}")
                else:
                    created_payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=amount,
                        payment_date=payment_date,
                        payment_method='mpesa',
                        transaction_reference=transaction_reference,
                        notes=(
                            f'M-Pesa STK payment. Account ref: {account_reference or "N/A"}. '
                            f'Phone: {phone_number or "N/A"}.'
                        ),
                    )
                    stk_request.payment = created_payment
                    logger.info(f"✅ STK Payment created: {created_payment.receipt_number}")
            except Exception as e:
                logger.error(f"Error creating STK payment: {e}", exc_info=True)

    stk_request.save()
    logger.info(f"✅ STK Callback processed: {checkout_request_id}")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def paybill_balance_result_callback(request):
    """
    Daraja account-balance result callback endpoint.
    Processes balance query results with improved balance extraction.
    """
    logger.info("=" * 60)
    logger.info("Balance Result Callback Received")
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in balance callback: {e}")
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'}, status=200)
    
    # ✅ Validate callback secret
    if not _callback_secret_is_valid(request):
        logger.warning("Unauthorized balance callback attempt - invalid secret")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized'}, status=403)
    
    result = payload.get('Result', {})
    result_code = result.get('ResultCode')
    result_desc = result.get('ResultDesc', '')
    
    logger.info(f"Result Code: {result_code}, Result Desc: {result_desc}")
    
    # ✅ Extract balance using improved function
    balance = None
    parameters = result.get('ResultParameters', {}).get('ResultParameter', [])
    
    if isinstance(parameters, list):
        for item in parameters:
            key = str(item.get('Key', '')).lower()
            value = item.get('Value')
            logger.info(f"Processing parameter: Key={key}")
            
            if key in {'accountbalance', 'availablebalance', 'balance'}:
                balance = _extract_account_balance(value)
                if balance is not None:
                    logger.info(f"✅ EXTRACTED BALANCE: {balance}")
                    break
    
    # If no balance found, log warning
    if balance is None:
        logger.warning("No balance could be extracted from the callback payload")
    
    # Determine status
    status = (
        PaybillBalanceSnapshot.STATUS_SUCCESS
        if str(result_code) == '0'
        else PaybillBalanceSnapshot.STATUS_FAILED
    )
    
    # ✅ Create snapshot with extracted balance
    snapshot = PaybillBalanceSnapshot.objects.create(
        status=status,
        available_balance=balance,
        conversation_id=str(result.get('ConversationID', '')).strip(),
        originator_conversation_id=str(result.get('OriginatorConversationID', '')).strip(),
        result_code=int(result_code) if str(result_code).lstrip('-').isdigit() else None,
        result_desc=result_desc,
        raw_payload=payload,
    )
    
    logger.info(f"✅ Balance snapshot created: ID={snapshot.id}, Balance={balance}, Status={status}")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'}, status=200)


@csrf_exempt
@require_POST
def paybill_balance_timeout_callback(request):
    """
    Daraja account-balance timeout callback endpoint.
    Handles timeout scenarios for balance queries.
    """
    logger.info("=" * 60)
    logger.info("Balance Timeout Callback Received")
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError:
        payload = {'raw': request.body.decode('utf-8', errors='ignore')}
        logger.warning(f"Invalid JSON in timeout callback: {payload}")
    
    # ✅ Validate callback secret
    if not _callback_secret_is_valid(request):
        logger.warning("Unauthorized timeout callback attempt - invalid secret")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Unauthorized callback'}, status=403)
    
    result = payload.get('Result', {}) if isinstance(payload, dict) else {}
    
    # ✅ Create timeout snapshot
    PaybillBalanceSnapshot.objects.create(
        status=PaybillBalanceSnapshot.STATUS_TIMEOUT,
        conversation_id=str(result.get('ConversationID', '')).strip(),
        originator_conversation_id=str(result.get('OriginatorConversationID', '')).strip(),
        result_desc='Daraja callback timeout',
        raw_payload=payload if isinstance(payload, dict) else {'payload': str(payload)},
    )
    
    logger.info("✅ Balance timeout recorded")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ==================== HELPER FUNCTIONS ====================

# Payment.PAYMENT_METHOD_CHOICES includes specific bank names (equity_hoza, dib_hoza, ...)
# since the finance ledger now captures *which account* separately via Payment.account,
# LedgerTransaction.payment_method only needs to capture *how* it was paid.
_LEDGER_PAYMENT_METHOD_MAP = {
    'cash': 'cash',
    'mpesa': 'mpesa',
    'bank_transfer': 'bank_transfer',
    'equity_hoza': 'bank_transfer',
    'dib_hoza': 'bank_transfer',
    'coop_hoza': 'bank_transfer',
    'kcb_ke': 'bank_transfer',
    'absa_ke': 'bank_transfer',
    'equity_ke': 'bank_transfer',
    'cheque': 'cheque',
    'card': 'card',
    'mixed': 'other',
    'other': 'other',
}


def _parse_payment_date(raw_value):
    """Parse a raw POST 'payment_date' string (split-payment branches build
    Payment via .objects.create() directly, bypassing PaymentForm's date
    cleaning). Falls back to today if missing/unparseable."""
    if not raw_value:
        return timezone.now().date()
    if isinstance(raw_value, str):
        try:
            return datetime.strptime(raw_value, '%Y-%m-%d').date()
        except ValueError:
            return timezone.now().date()
    return raw_value


def _record_finance_ledger_entry(payment, client_vehicle):
    """
    Post a credit entry to the payment's receiving account and return it.
    Returns None if no account was selected (older payments, or automated
    inflows such as M-Pesa callbacks that aren't yet reconciled to an account).
    """
    if not payment.account:
        return None

    from apps.finance import services as finance_services

    has_plan = InstallmentPlan.objects.filter(client_vehicle=client_vehicle, is_active=True).exists()
    return finance_services.create_transaction(
        payment.account,
        direction='credit',
        transaction_type='hire_purchase_instalment' if has_plan else 'client_vehicle_payment',
        amount=payment.amount,
        created_by=payment.recorded_by,
        transaction_date=payment.payment_date,
        source_module='payments',
        related_client=client_vehicle.client,
        related_vehicle=client_vehicle.vehicle,
        payment_method=_LEDGER_PAYMENT_METHOD_MAP.get(payment.payment_method, 'other'),
        description=f'Payment {payment.receipt_number} - {client_vehicle.vehicle}',
    )


def _snapshot_pending_schedule_amounts(client_vehicle):
    """
    Capture each pending instalment's amount_paid *before* a new payment is
    applied, so the amount a specific payment actually settles can be
    computed afterward by diffing.

    NOTE: schedules are marked paid automatically by the
    update_payment_schedules_after_payment signal in payments/signals1.py
    (registered in PaymentsConfig.ready()), which runs synchronously inside
    Payment.save(). There used to be a second, manual pass over the same
    schedules here in views.py that duplicated the signal's work — that was
    a real bug (every payment double-applied: instalments got marked paid
    twice and totals were double-counted). Do not reintroduce a second
    schedule-marking pass; only read state after save() and diff it.
    """
    try:
        plan = client_vehicle.installment_plan
    except InstallmentPlan.DoesNotExist:
        return {}
    return {
        schedule.pk: schedule.amount_paid
        for schedule in plan.payment_schedules.filter(is_paid=False)
    }


def _allocate_ledger_transaction_to_schedules(ledger_transaction, client_vehicle, pre_save_amounts):
    """
    Diff each instalment's amount_paid against its pre-payment snapshot
    (see _snapshot_pending_schedule_amounts) to determine how much of
    ledger_transaction it consumed, and record that as a PaymentAllocation.
    Must be called after the triggering Payment has been saved.
    """
    if not ledger_transaction or not pre_save_amounts:
        return

    from apps.finance.models import PaymentAllocation

    try:
        plan = client_vehicle.installment_plan
    except InstallmentPlan.DoesNotExist:
        return

    schedules = plan.payment_schedules.filter(pk__in=pre_save_amounts.keys())
    for schedule in schedules:
        applied = schedule.amount_paid - pre_save_amounts.get(schedule.pk, Decimal('0.00'))
        if applied > 0:
            PaymentAllocation.objects.create(
                transaction=ledger_transaction,
                payment_schedule=schedule,
                amount_allocated=applied,
            )


@login_required
def defaulters_report(request):
    """
    Generate report of clients with outstanding vehicle balances.
    Source of truth: ClientVehicle.balance > 0 (not limited to clients with
    formal overdue PaymentSchedule records — that approach misses clients who
    owe money but have no installment plan or whose first scheduled payment has
    not yet been recorded as overdue).
    """
    today = timezone.now().date()

    # Find every vehicle purchase that still has an outstanding balance.
    # Exclude deactivated records (repossessed vehicles).
    outstanding_cvs = ClientVehicle.objects.filter(
        balance__gt=0,
        is_paid_off=False,
        is_active=True,
    ).select_related('client', 'vehicle').order_by('purchase_date')

    defaulters = {}
    for cv in outstanding_cvs:
        client = cv.client

        # Find the oldest unpaid, past-due installment for this vehicle.
        overdue_qs = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle=cv,
            installment_plan__is_active=True,
            is_paid=False,
            due_date__lt=today,
        ).order_by('due_date')
        oldest_overdue = overdue_qs.first()
        overdue_count = overdue_qs.count()

        if oldest_overdue:
            days_overdue = oldest_overdue.days_overdue
        else:
            # No formal overdue schedule — measure from purchase date.
            days_overdue = (today - cv.purchase_date).days

        last_payment = Payment.objects.filter(
            client_vehicle=cv
        ).order_by('-payment_date', '-created_at').first()

        if client.id not in defaulters:
            defaulters[client.id] = {
                'client': client,
                'vehicle': cv.vehicle,
                'client_vehicle_id': cv.id,
                'days_overdue': days_overdue,
                'overdue_installments': overdue_count,
                'total_outstanding': cv.balance,
                'payment_percentage': Decimal('0.00'),
                'last_payment_date': last_payment.payment_date if last_payment else None,
                'last_payment_amount': last_payment.amount if last_payment else None,
            }
        else:
            # Client with multiple vehicles — accumulate balance, take worst overdue.
            defaulters[client.id]['total_outstanding'] += cv.balance
            defaulters[client.id]['overdue_installments'] += overdue_count
            if days_overdue > defaulters[client.id]['days_overdue']:
                defaulters[client.id]['days_overdue'] = days_overdue

    # Compute payment_percentage from purchase_price vs total_paid across all vehicles.
    for client_id, data in defaulters.items():
        cv_totals = ClientVehicle.objects.filter(client=data['client']).aggregate(
            total_purchase=Sum('purchase_price'),
            total_paid_sum=Sum('total_paid'),
        )
        total_purchase = cv_totals['total_purchase'] or Decimal('0.00')
        total_paid_cv = cv_totals['total_paid_sum'] or Decimal('0.00')
        if total_purchase > 0:
            data['payment_percentage'] = (total_paid_cv / total_purchase) * Decimal('100')

    defaulters_list = sorted(defaulters.values(), key=lambda d: d['days_overdue'], reverse=True)
    total_outstanding = sum((d['total_outstanding'] for d in defaulters_list), Decimal('0.00'))

    critical_defaulters = [d for d in defaulters_list if d['days_overdue'] >= 90]
    severe_defaulters = [d for d in defaulters_list if 60 <= d['days_overdue'] < 90]
    moderate_defaulters = [d for d in defaulters_list if 30 <= d['days_overdue'] < 60]

    critical_amount = sum((d['total_outstanding'] for d in critical_defaulters), Decimal('0.00'))
    severe_amount = sum((d['total_outstanding'] for d in severe_defaulters), Decimal('0.00'))
    moderate_amount = sum((d['total_outstanding'] for d in moderate_defaulters), Decimal('0.00'))

    average_days_overdue = Decimal('0.00')
    if defaulters_list:
        average_days_overdue = (
            sum((Decimal(str(d['days_overdue'])) for d in defaulters_list), Decimal('0.00'))
            / Decimal(str(len(defaulters_list)))
        )

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
        'now': timezone.now(),
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