"""
Views for the payments app
Handles payment recording, installment plans, schedules, and reporting
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta
import csv
import json
import re
import logging

from .models1 import (
    Payment,
    PaymentSplit,
    AccountWithdrawal,
    InstallmentPlan,
    PaymentSchedule,
    PaymentReminder,
    MpesaSTKRequest,
    PaybillTransaction,
    PaybillBalanceSnapshot,
    Account,
    AccountTransaction,
    AccountTransfer,
    Reconciliation,
)
from .daraja import (
    request_account_balance, mpesa_is_configured, get_missing_mpesa_vars,
    initiate_stk_push, _normalize_phone_number, register_c2b_urls,
)
from .callback_debug import log_incoming_callback
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


def _request_paybill_balance():
    """Initiate an asynchronous paybill balance request and store a pending snapshot."""
    try:
        result = request_account_balance()
        if result.get('ok'):
            response_payload = result.get('response', {})
            PaybillBalanceSnapshot.objects.create(
                status=PaybillBalanceSnapshot.STATUS_PENDING,
                request_reference=result.get('request_reference', ''),
                conversation_id=response_payload.get('ConversationID', ''),
                originator_conversation_id=response_payload.get('OriginatorConversationID', ''),
                result_desc=response_payload.get('ResponseDescription', ''),
                raw_payload=response_payload,
            )
            logger.info('Paybill balance request initiated from tracker view.')
            return True
        logger.warning('Paybill balance request failed: %s', result.get('error'))
    except Exception as exc:
        logger.error('Error requesting paybill balance: %s', exc, exc_info=True)
    return False


def _find_pending_balance_snapshot(conversation_id, originator_id):
    """Locate the pending snapshot a Daraja balance callback belongs to."""
    pending = PaybillBalanceSnapshot.objects.filter(
        status=PaybillBalanceSnapshot.STATUS_PENDING
    )
    match = Q()
    if conversation_id:
        match |= Q(conversation_id=conversation_id)
    if originator_id:
        match |= Q(originator_conversation_id=originator_id)
    if match:
        snapshot = pending.filter(match).order_by('-created_at').first()
        if snapshot:
            return snapshot
    # Daraja occasionally echoes different conversation ids than the ones
    # returned at request time — fall back to the most recent pending request.
    return pending.order_by('-created_at').first()


def _should_request_paybill_balance_on_load():
    """Return True when a tracker page load should issue a new balance request."""
    latest_snapshot = PaybillBalanceSnapshot.objects.order_by('-created_at').first()
    if not latest_snapshot:
        return True

    if latest_snapshot.status == PaybillBalanceSnapshot.STATUS_PENDING:
        # There is already an in-flight balance request. Treat one that never
        # received its callback as abandoned so it can't block refreshes forever.
        age = timezone.now() - latest_snapshot.created_at
        return age > timedelta(minutes=10)

    if latest_snapshot.status == PaybillBalanceSnapshot.STATUS_SUCCESS:
        age = timezone.now() - latest_snapshot.created_at
        # Avoid creating a new request on every page load if the latest
        # successful balance is still fresh.
        return age > timedelta(minutes=5)

    return True


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
    """
    Validate the callback secret embedded in the callback URL's query string.

    Daraja's C2B/STK/balance webhooks POST straight to whatever URL was
    registered with Safaricom and never carry custom headers, so the secret
    is embedded in the URL itself (see daraja._with_callback_secret) rather
    than checked via an HTTP header, which real Safaricom traffic can never
    supply.
    """
    expected_secret = str(getattr(settings, 'MPESA_CALLBACK_SECRET', '') or '').strip()

    if not expected_secret:
        return True

    provided_secret = (request.GET.get('callback_secret') or '').strip()
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
        initial = {}
        preselect = request.GET.get('payment_method')
        if preselect in dict(AccountWithdrawal.PAYMENT_METHOD_CHOICES):
            initial['payment_method'] = preselect
        form = AccountWithdrawalForm(initial=initial)

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
def account_transactions(request, method):
    """
    Unified transaction history (additions, reversed payments and
    withdrawals) for a single HOZA/KE sub-account, so a specific account
    (e.g. Equity Hoza) can be audited without combing through the full
    payment list.
    """
    method_labels = dict(AccountWithdrawal.PAYMENT_METHOD_CHOICES)
    if method not in method_labels:
        messages.error(request, 'Unknown account.')
        return redirect('payments:payment_list')

    label = method_labels[method]
    transactions = []

    direct_payments = Payment.objects.filter(payment_method=method).select_related(
        'client_vehicle__client', 'client_vehicle__vehicle', 'recorded_by'
    )
    for payment in direct_payments:
        transactions.append({
            'date': payment.payment_date,
            'sort_key': payment.created_at,
            'type': 'reversed' if payment.is_reversed else 'addition',
            'amount': payment.amount,
            'reference': payment.transaction_reference or payment.receipt_number,
            'client': payment.client_vehicle.client,
            'detail_url': reverse('payments:payment_detail', args=[payment.pk]),
            'recorded_by': payment.recorded_by,
        })

    split_payments = PaymentSplit.objects.filter(payment_method=method).select_related(
        'payment__client_vehicle__client', 'payment__client_vehicle__vehicle', 'payment__recorded_by'
    )
    for split in split_payments:
        payment = split.payment
        transactions.append({
            'date': payment.payment_date,
            'sort_key': split.created_at,
            'type': 'reversed' if payment.is_reversed else 'addition',
            'amount': split.amount,
            'reference': split.transaction_reference or payment.receipt_number,
            'client': payment.client_vehicle.client,
            'detail_url': reverse('payments:payment_detail', args=[payment.pk]),
            'recorded_by': payment.recorded_by,
        })

    withdrawals = AccountWithdrawal.objects.filter(payment_method=method).select_related('recorded_by')
    for withdrawal in withdrawals:
        transactions.append({
            'date': withdrawal.withdrawal_date,
            'sort_key': withdrawal.created_at,
            'type': 'withdrawal',
            'amount': withdrawal.amount,
            'reference': withdrawal.reason,
            'client': None,
            'detail_url': None,
            'recorded_by': withdrawal.recorded_by,
        })

    transactions.sort(key=lambda t: (t['date'], t['sort_key']), reverse=True)

    total_additions = sum((t['amount'] for t in transactions if t['type'] == 'addition'), Decimal('0.00'))
    total_reversed = sum((t['amount'] for t in transactions if t['type'] == 'reversed'), Decimal('0.00'))
    total_withdrawals = sum((t['amount'] for t in transactions if t['type'] == 'withdrawal'), Decimal('0.00'))
    net_total = total_additions - total_withdrawals

    paginator = Paginator(transactions, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'method': method,
        'label': label,
        'is_hoza': method in AccountWithdrawal.HOZA_METHODS,
        'transactions': page_obj,
        'total_additions': total_additions,
        'total_reversed': total_reversed,
        'total_withdrawals': total_withdrawals,
        'net_total': net_total,
    }

    log_audit(request.user, 'view', 'Payment', f'Viewed {label} account transactions')
    return render(request, 'payments/account_transactions.html', context)


# ==================== FINANCE ACCOUNT BREAKDOWN VIEWS ====================

CATEGORY_LABELS = {'hoza': 'Hoza', 'ke': 'KE'}


def _is_approver(user):
    """
    True for users trusted to self-approve account-level actions immediately
    (same tier as account create/edit/deactivate). Everyone else's account
    transactions/transfers queue as pending until an approver reviews them.
    """
    if user.is_superuser:
        return True
    from apps.permissions.models import RolePermission
    try:
        permission = RolePermission.objects.get(role=user.role, module_name='payments')
    except RolePermission.DoesNotExist:
        return False
    return permission.access_level == AccessLevel.FULL_ACCESS


@login_required
def account_breakdown(request, category):
    """Full-page account breakdown for the Hoza or KE category (replaces the old modal)."""
    if category not in CATEGORY_LABELS:
        messages.error(request, 'Unknown account category.')
        return redirect('payments:payment_list')

    accounts = list(Account.objects.filter(category=category))

    ZERO = Decimal('0.00')
    summary = {
        'opening_balance': ZERO,
        'money_in': ZERO,
        'money_out': ZERO,
        'transfers_in': ZERO,
        'transfers_out': ZERO,
        'current_balance': ZERO,
    }
    for account in accounts:
        account.computed_money_in = account.money_in_total
        account.computed_money_out = account.money_out_total
        account.computed_transfers_in = account.transfers_in_total
        account.computed_transfers_out = account.transfers_out_total
        account.computed_balance = account.current_balance

        summary['opening_balance'] += account.opening_balance
        summary['money_in'] += account.computed_money_in
        summary['money_out'] += account.computed_money_out
        summary['transfers_in'] += account.computed_transfers_in
        summary['transfers_out'] += account.computed_transfers_out
        summary['current_balance'] += account.computed_balance

    pending_approvals = AccountTransaction.objects.filter(
        account__category=category, approval_status='pending'
    ).count()

    context = {
        'category': category,
        'category_label': CATEGORY_LABELS[category],
        'is_hoza': category == 'hoza',
        'accounts': accounts,
        'summary': summary,
        'pending_approvals': pending_approvals,
    }

    log_audit(request.user, 'view', 'Account', f'Viewed {CATEGORY_LABELS[category]} account breakdown')
    return render(request, 'payments/account_breakdown.html', context)


@login_required
def account_detail(request, pk):
    """Full ledger for a single account: opening balance, totals and full transaction history."""
    account = get_object_or_404(Account, pk=pk)

    rows = []

    for payment in account._legacy_payment_qs().select_related(
        'client_vehicle__client', 'client_vehicle__vehicle', 'recorded_by'
    ).exclude(splits__isnull=False):
        rows.append({
            'date': payment.payment_date,
            'sort_key': payment.created_at,
            'reference': payment.transaction_reference or payment.receipt_number,
            'type_label': 'Client Payment',
            'narration': payment.notes or '',
            'related_client': payment.client_vehicle.client,
            'related_vehicle': payment.client_vehicle.vehicle,
            'payment_method': payment.get_payment_method_display(),
            'money_in': payment.amount,
            'money_out': Decimal('0.00'),
            'created_by': payment.recorded_by,
            'approval_status': 'approved',
            'reconciliation_status': '—',
            'detail_url': reverse('payments:payment_detail', args=[payment.pk]),
        })

    for split in account._legacy_split_qs().select_related(
        'payment__client_vehicle__client', 'payment__client_vehicle__vehicle', 'payment__recorded_by'
    ):
        payment = split.payment
        rows.append({
            'date': payment.payment_date,
            'sort_key': split.created_at,
            'reference': split.transaction_reference or payment.receipt_number,
            'type_label': 'Client Payment (split)',
            'narration': payment.notes or '',
            'related_client': payment.client_vehicle.client,
            'related_vehicle': payment.client_vehicle.vehicle,
            'payment_method': split.get_payment_method_display(),
            'money_in': split.amount,
            'money_out': Decimal('0.00'),
            'created_by': payment.recorded_by,
            'approval_status': 'approved',
            'reconciliation_status': '—',
            'detail_url': reverse('payments:payment_detail', args=[payment.pk]),
        })

    for withdrawal in account._legacy_withdrawal_qs().select_related('recorded_by'):
        rows.append({
            'date': withdrawal.withdrawal_date,
            'sort_key': withdrawal.created_at,
            'reference': None,
            'type_label': 'Withdrawal',
            'narration': withdrawal.reason or '',
            'related_client': None,
            'related_vehicle': None,
            'payment_method': withdrawal.get_payment_method_display(),
            'money_in': Decimal('0.00'),
            'money_out': withdrawal.amount,
            'created_by': withdrawal.recorded_by,
            'approval_status': 'approved',
            'reconciliation_status': '—',
            'detail_url': None,
        })

    for txn in account.transactions.select_related(
        'created_by', 'related_client', 'related_vehicle'
    ).prefetch_related('reconciliations'):
        latest_reconciliation = txn.reconciliations.order_by('-created_at').first()
        # Reversed entries stay visible for audit but no longer affect the running balance.
        money_in = Decimal('0.00') if txn.is_reversed else (txn.amount if txn.direction == 'in' else Decimal('0.00'))
        money_out = Decimal('0.00') if txn.is_reversed else (txn.amount if txn.direction == 'out' else Decimal('0.00'))
        rows.append({
            'date': txn.date,
            'sort_key': txn.created_at,
            'reference': txn.reference,
            'type_label': txn.get_transaction_type_display(),
            'narration': txn.narration,
            'related_client': txn.related_client,
            'related_vehicle': txn.related_vehicle,
            'payment_method': txn.payment_method,
            'money_in': money_in,
            'money_out': money_out,
            'display_amount': txn.amount,
            'display_direction': txn.direction,
            'created_by': txn.created_by,
            'approval_status': txn.approval_status,
            'is_reversed': txn.is_reversed,
            'reconciliation_status': latest_reconciliation.get_status_display() if latest_reconciliation else '—',
            'detail_url': None,
            'transaction_pk': txn.pk,
            'can_reconcile': not txn.is_reversed,
        })

    rows.sort(key=lambda r: (r['date'], r['sort_key']))
    running = account.opening_balance
    for row in rows:
        running += row['money_in'] - row['money_out']
        row['running_balance'] = running
    rows.reverse()

    paginator = Paginator(rows, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'account': account,
        'opening_balance': account.opening_balance,
        'money_in_total': account.money_in_total,
        'money_out_total': account.money_out_total,
        'transfers_in_total': account.transfers_in_total,
        'transfers_out_total': account.transfers_out_total,
        'current_balance': account.current_balance,
        'pending_balance': account.pending_balance,
        'pending_count': account.transactions.filter(approval_status='pending').count(),
        'rows': page_obj,
    }

    log_audit(request.user, 'view', 'Account', f'Viewed ledger for {account.name}')
    return render(request, 'payments/account_detail.html', context)


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
def account_create(request):
    """Create a new finance account."""
    from .forms import AccountForm

    initial = {}
    preselect = request.GET.get('category')
    if preselect in CATEGORY_LABELS:
        initial['category'] = preselect

    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.created_by = request.user
            account.save()
            log_audit(request.user, 'create', 'Account', f'Created account {account.name}')
            messages.success(request, f'Account "{account.name}" created.')
            return redirect('payments:account_detail', pk=account.pk)
    else:
        form = AccountForm(initial=initial)

    return render(request, 'payments/account_form.html', {'form': form, 'is_edit': False})


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
def account_edit(request, pk):
    """Edit an existing finance account."""
    from .forms import AccountForm

    account = get_object_or_404(Account, pk=pk)

    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'update', 'Account', f'Edited account {account.name}')
            messages.success(request, f'Account "{account.name}" updated.')
            return redirect('payments:account_detail', pk=account.pk)
    else:
        form = AccountForm(instance=account)

    return render(request, 'payments/account_form.html', {'form': form, 'is_edit': True, 'account': account})


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_deactivate(request, pk):
    """Deactivate an account. Never deletes — history remains intact."""
    account = get_object_or_404(Account, pk=pk)
    account.is_active = False
    account.save(update_fields=['is_active', 'updated_at'])
    log_audit(request.user, 'update', 'Account', f'Deactivated account {account.name}')
    messages.success(request, f'Account "{account.name}" deactivated.')
    return redirect('payments:account_detail', pk=account.pk)


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_activate(request, pk):
    """Reactivate a previously deactivated account."""
    account = get_object_or_404(Account, pk=pk)
    account.is_active = True
    account.save(update_fields=['is_active', 'updated_at'])
    log_audit(request.user, 'update', 'Account', f'Reactivated account {account.name}')
    messages.success(request, f'Account "{account.name}" reactivated.')
    return redirect('payments:account_detail', pk=account.pk)


@login_required
@module_permission_required('payments', AccessLevel.READ_WRITE)
def account_transaction_create(request, pk):
    """Record a manual transaction directly against an account."""
    from .forms import AccountTransactionForm

    account = get_object_or_404(Account, pk=pk)

    if not account.is_active:
        messages.error(request, f'"{account.name}" is inactive and cannot receive new transactions.')
        return redirect('payments:account_detail', pk=account.pk)

    if request.method == 'POST':
        form = AccountTransactionForm(request.POST, request.FILES)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.account = account
            txn.created_by = request.user
            txn.approval_status = 'approved' if _is_approver(request.user) else 'pending'
            txn.save()
            log_audit(
                request.user, 'create', 'AccountTransaction',
                f'Recorded {txn.get_transaction_type_display()} of KES {txn.amount:,.2f} on {account.name} '
                f'({txn.approval_status})'
            )
            if txn.approval_status == 'pending':
                messages.success(request, 'Transaction submitted for approval.')
            else:
                messages.success(request, 'Transaction recorded.')
            return redirect('payments:account_detail', pk=account.pk)
    else:
        form = AccountTransactionForm()

    return render(request, 'payments/account_transaction_form.html', {'form': form, 'account': account})


@login_required
@module_permission_required('payments', AccessLevel.READ_WRITE)
def account_transfer_create(request):
    """Transfer funds between two active accounts."""
    from .forms import AccountTransferForm

    initial = {}
    source_pk = request.GET.get('source')
    if source_pk:
        initial['source_account'] = source_pk

    if request.method == 'POST':
        form = AccountTransferForm(request.POST)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.created_by = request.user
            transfer.status = 'approved' if _is_approver(request.user) else 'pending'
            try:
                transfer.full_clean()
            except DjangoValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
                return render(request, 'payments/account_transfer_form.html', {'form': form})
            transfer.save()
            transfer.execute(request.user)
            log_audit(
                request.user, 'create', 'AccountTransfer',
                f'Transferred KES {transfer.amount:,.2f} from {transfer.source_account.name} '
                f'to {transfer.destination_account.name} ({transfer.status})'
            )
            if transfer.status == 'pending':
                messages.success(request, 'Transfer submitted for approval.')
            else:
                messages.success(request, 'Transfer completed.')
            return redirect('payments:account_detail', pk=transfer.source_account.pk)
    else:
        form = AccountTransferForm(initial=initial)

    return render(request, 'payments/account_transfer_form.html', {'form': form})


@login_required
@module_permission_required('payments', AccessLevel.READ_WRITE)
def reconciliation_create(request, transaction_pk):
    """Request a reconciliation against a wrongly-posted account transaction."""
    from .forms import ReconciliationForm

    original = get_object_or_404(AccountTransaction, pk=transaction_pk)

    if original.is_reversed:
        messages.error(request, 'This transaction has already been reversed and cannot be reconciled again.')
        return redirect('payments:account_detail', pk=original.account.pk)

    if request.method == 'POST':
        # original_transaction is set on the instance before validation, since it's
        # excluded from the form fields but Reconciliation.clean() requires it to be set.
        form = ReconciliationForm(request.POST, instance=Reconciliation(original_transaction=original))
        if form.is_valid():
            reconciliation = form.save(commit=False)
            reconciliation.initiated_by = request.user
            try:
                reconciliation.full_clean()
            except DjangoValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
                return render(request, 'payments/reconciliation_form.html', {'form': form, 'original': original})
            reconciliation.save()
            log_audit(
                request.user, 'create', 'Reconciliation',
                f'Requested reconciliation ({reconciliation.get_issue_type_display()}) on transaction #{original.pk}'
            )
            messages.success(request, 'Reconciliation request submitted for approval.')
            return redirect('payments:account_detail', pk=original.account.pk)
    else:
        form = ReconciliationForm()

    return render(request, 'payments/reconciliation_form.html', {'form': form, 'original': original})


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
def approval_queue(request):
    """List everything awaiting approval: transactions, transfers, reconciliations, plus suspense accounts."""
    pending_transfers = AccountTransfer.objects.filter(status='pending').select_related(
        'source_account', 'destination_account', 'created_by'
    )
    transfer_entry_ids = AccountTransaction.objects.filter(
        transfer__in=pending_transfers
    ).values_list('id', flat=True)

    pending_transactions = AccountTransaction.objects.filter(
        approval_status='pending'
    ).exclude(id__in=transfer_entry_ids).select_related('account', 'created_by', 'related_client', 'related_vehicle')

    pending_reconciliations = Reconciliation.objects.filter(status='pending').select_related(
        'original_transaction__account', 'initiated_by', 'correct_account', 'correct_client', 'correct_vehicle'
    )

    suspense_accounts = Account.objects.filter(is_suspense=True)

    context = {
        'pending_transactions': pending_transactions,
        'pending_transfers': pending_transfers,
        'pending_reconciliations': pending_reconciliations,
        'suspense_accounts': suspense_accounts,
    }

    log_audit(request.user, 'view', 'Account', 'Viewed finance approval queue')
    return render(request, 'payments/approval_queue.html', context)


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_transaction_approve(request, pk):
    txn = get_object_or_404(AccountTransaction, pk=pk)
    txn.approve(request.user)
    log_audit(request.user, 'update', 'AccountTransaction', f'Approved transaction #{txn.pk} on {txn.account.name}')
    messages.success(request, 'Transaction approved.')
    return redirect('payments:approval_queue')


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_transaction_reject(request, pk):
    txn = get_object_or_404(AccountTransaction, pk=pk)
    txn.reject(request.user)
    log_audit(request.user, 'update', 'AccountTransaction', f'Rejected transaction #{txn.pk} on {txn.account.name}')
    messages.success(request, 'Transaction rejected.')
    return redirect('payments:approval_queue')


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_transfer_approve(request, pk):
    transfer = get_object_or_404(AccountTransfer, pk=pk)
    with transaction.atomic():
        transfer.status = 'approved'
        transfer.approved_by = request.user
        transfer.approved_at = timezone.now()
        transfer.save(update_fields=['status', 'approved_by', 'approved_at'])
        for entry in transfer.ledger_entries.all():
            entry.approve(request.user)
    log_audit(
        request.user, 'update', 'AccountTransfer',
        f'Approved transfer #{transfer.pk}: {transfer.source_account.name} -> {transfer.destination_account.name}'
    )
    messages.success(request, 'Transfer approved.')
    return redirect('payments:approval_queue')


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def account_transfer_reject(request, pk):
    transfer = get_object_or_404(AccountTransfer, pk=pk)
    with transaction.atomic():
        transfer.status = 'rejected'
        transfer.approved_by = request.user
        transfer.approved_at = timezone.now()
        transfer.save(update_fields=['status', 'approved_by', 'approved_at'])
        for entry in transfer.ledger_entries.all():
            entry.reject(request.user)
    log_audit(
        request.user, 'update', 'AccountTransfer',
        f'Rejected transfer #{transfer.pk}: {transfer.source_account.name} -> {transfer.destination_account.name}'
    )
    messages.success(request, 'Transfer rejected.')
    return redirect('payments:approval_queue')


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def reconciliation_approve(request, pk):
    reconciliation = get_object_or_404(Reconciliation, pk=pk)
    try:
        reconciliation.approve(request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('payments:approval_queue')
    log_audit(request.user, 'update', 'Reconciliation', f'Approved reconciliation #{reconciliation.pk}')
    messages.success(request, 'Reconciliation approved.')
    return redirect('payments:approval_queue')


@login_required
@module_permission_required('payments', AccessLevel.FULL_ACCESS)
@require_POST
def reconciliation_reject(request, pk):
    reconciliation = get_object_or_404(Reconciliation, pk=pk)
    try:
        reconciliation.reject(request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('payments:approval_queue')
    log_audit(request.user, 'update', 'Reconciliation', f'Rejected reconciliation #{reconciliation.pk}')
    messages.success(request, 'Reconciliation rejected.')
    return redirect('payments:approval_queue')


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
        # payment_progress can exceed 100% on an overpaid vehicle — cap only
        # the bar's width so it doesn't overflow its container; the exact
        # percentage is still shown as text next to it.
        'progress_bar_percent': min(payment.client_vehicle.payment_progress, 100),
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
    from .models1 import PaymentSplit
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    if request.method == 'POST':
        # Default form for re-rendering the page on any failure path below —
        # the split-payment branch doesn't build one of its own.
        form = PaymentForm(request.POST)

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
                    payment_date = parse_date(request.POST.get('payment_date', '')) or timezone.now().date()

                    # Create main payment with MIXED method
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=payment_date,
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

                    # Balance, payment schedules, and client status are already
                    # updated by the Payment post_save signals — refresh to read
                    # those computed values instead of re-applying them here.
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
                            ][1]} KES {Decimal(a):,.2f}"
                            for m, a, _, _ in valid_splits
                        ])
                        messages.success(
                            request,
                            f'Split payment of KES {payment.amount:,.2f} recorded! '
                            f'({split_summary}) — '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )

                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )

                    return redirect('payments:payment_detail', pk=payment.pk)

                except (ValueError, InvalidOperation) as e:
                    messages.error(request, f'Invalid split amounts: {str(e)}')
        else:
            # Single payment (traditional flow)
            if form.is_valid():
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.client_vehicle = client_vehicle
                    payment.recorded_by = request.user
                    payment.save()

                    # Balance, payment schedules, and client status are already
                    # updated by the Payment post_save signals — refresh to read
                    # those computed values instead of re-applying them here.
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
    from .models1 import PaymentSplit

    if request.method == 'POST':
        # Resolve the selected client vehicle up front — both the split and
        # single-payment flows below need it, and the template re-render on
        # any failure path needs `client_vehicle`/`form` to always be defined.
        client_vehicle_id = request.POST.get('client_vehicle')
        try:
            client_vehicle = ClientVehicle.objects.select_related('client', 'vehicle').get(pk=client_vehicle_id)
        except (ClientVehicle.DoesNotExist, ValueError, TypeError):
            client_vehicle = None

        form = PaymentForm(request.POST, client_vehicle=client_vehicle)

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

        if not client_vehicle:
            messages.error(request, 'Please select a client vehicle.')
        elif valid_splits and len(valid_splits) > 1:
            # Multi-split payment
            with transaction.atomic():
                try:
                    # Calculate total from splits
                    total_amount = sum(Decimal(a) for _, a, _, _ in valid_splits)
                    payment_date = parse_date(request.POST.get('payment_date', '')) or timezone.now().date()

                    # Create main payment with MIXED method
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=total_amount,
                        payment_date=payment_date,
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

                    # Balance, payment schedules, and client status are already
                    # updated by the Payment post_save signals — refresh to read
                    # those computed values instead of re-applying them here.
                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
                        messages.success(request, f'Split payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Split payment of KES {payment.amount:,.2f} recorded! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )

                    log_audit(
                        request.user, 'create', 'Payment',
                        f'Recorded split payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                    )

                    return redirect('payments:payment_detail', pk=payment.pk)

                except (ValueError, InvalidOperation, ClientVehicle.DoesNotExist) as e:
                    messages.error(request, f'Error processing split payment: {str(e)}')
        else:
            # Single payment (traditional flow)
            if form.is_valid():
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.client_vehicle = client_vehicle
                    payment.recorded_by = request.user
                    payment.save()

                    # Balance, payment schedules, and client status are already
                    # updated by the Payment post_save signals — refresh to read
                    # those computed values instead of re-applying them here.
                    client_vehicle.refresh_from_db()

                    if client_vehicle.is_paid_off:
                        messages.success(request, f'Payment recorded! Vehicle fully paid off! 🎉')
                    else:
                        messages.success(
                            request,
                            f'Payment of KES {payment.amount:,.2f} recorded successfully! '
                            f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                        )

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
        client_vehicle = None

        if client_vehicle_id:
            try:
                client_vehicle = ClientVehicle.objects.select_related('client', 'vehicle').get(pk=client_vehicle_id)
            except ClientVehicle.DoesNotExist:
                pass

        form = PaymentForm(client_vehicle=client_vehicle)
    
    # Get client vehicles with outstanding balances — full list for the
    # dropdown, most-recent slice for the sidebar quick-pick cards.
    outstanding_client_vehicles = ClientVehicle.objects.select_related(
        'client', 'vehicle'
    ).filter(
        is_paid_off=False,
        balance__gt=0
    ).order_by('client__first_name', 'client__last_name')
    recent_client_vehicles = outstanding_client_vehicles.order_by('-purchase_date')[:20]

    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'client_vehicle_choices': outstanding_client_vehicles,
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

    # Refresh the paybill balance only when needed on page load.
    if _should_request_paybill_balance_on_load():
        _request_paybill_balance()

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

    # Per-paybill breakdown — configured shortcodes plus any others that have
    # actually received transactions (never hardcode: the .env shortcodes are
    # the source of truth for which paybills exist).
    configured_paybills = [
        str(getattr(settings, 'MPESA_SHORTCODE', '') or '').strip(),
        str(getattr(settings, 'MPESA_SHORTCODE_2', '') or '').strip(),
    ]
    seen_paybills = list(
        all_transactions.exclude(business_short_code='')
        .values_list('business_short_code', flat=True)
        .distinct()
    )
    known_paybills = [code for code in dict.fromkeys(configured_paybills + seen_paybills) if code]
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
    if _request_paybill_balance():
        messages.success(request, 'Balance request sent to Daraja. Awaiting callback result.')
    else:
        messages.error(request, 'Unable to request paybill balance. Check server logs for details.')

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

    # Surface exactly what was submitted and what Safaricom said back per
    # shortcode — a bare "success" hides whether Daraja actually accepted the
    # URL change on an already-registered production shortcode.
    for r in results:
        desc = (r.get('response') or {}).get('ResponseDescription') or r.get('error') or 'No response description.'
        detail = (
            f"Paybill {r.get('code')}: {'OK' if r.get('ok') else 'FAILED'} — {desc} "
            f"(Confirmation: {r.get('confirmation_url', 'n/a')})"
        )
        if r.get('ok'):
            messages.info(request, detail)
        else:
            messages.error(request, detail)
        logger.info(f"C2B registration result — {detail}")

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

@log_incoming_callback('paybill_validation_callback')
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


@log_incoming_callback('paybill_confirmation_callback')
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


@log_incoming_callback('stk_push_callback')
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


@log_incoming_callback('paybill_balance_result_callback')
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

    conversation_id = str(result.get('ConversationID', '')).strip()
    originator_id = str(result.get('OriginatorConversationID', '')).strip()

    # Resolve the pending snapshot created when the request was initiated —
    # creating a separate row would leave that one "pending" forever.
    snapshot = _find_pending_balance_snapshot(conversation_id, originator_id)
    if snapshot:
        snapshot.status = status
        snapshot.available_balance = balance
        snapshot.conversation_id = conversation_id or snapshot.conversation_id
        snapshot.originator_conversation_id = originator_id or snapshot.originator_conversation_id
        snapshot.result_code = int(result_code) if str(result_code).lstrip('-').isdigit() else None
        snapshot.result_desc = result_desc
        snapshot.raw_payload = payload
        snapshot.save()
    else:
        snapshot = PaybillBalanceSnapshot.objects.create(
            status=status,
            available_balance=balance,
            conversation_id=conversation_id,
            originator_conversation_id=originator_id,
            result_code=int(result_code) if str(result_code).lstrip('-').isdigit() else None,
            result_desc=result_desc,
            raw_payload=payload,
        )

    logger.info(f"✅ Balance snapshot resolved: ID={snapshot.id}, Balance={balance}, Status={status}")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'}, status=200)


@log_incoming_callback('paybill_balance_timeout_callback')
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

    conversation_id = str(result.get('ConversationID', '')).strip()
    originator_id = str(result.get('OriginatorConversationID', '')).strip()

    # Resolve the pending snapshot rather than leaving it stuck alongside a
    # separate timeout row.
    snapshot = _find_pending_balance_snapshot(conversation_id, originator_id)
    if snapshot:
        snapshot.status = PaybillBalanceSnapshot.STATUS_TIMEOUT
        snapshot.result_desc = 'Daraja callback timeout'
        snapshot.raw_payload = payload if isinstance(payload, dict) else {'payload': str(payload)}
        snapshot.save()
    else:
        PaybillBalanceSnapshot.objects.create(
            status=PaybillBalanceSnapshot.STATUS_TIMEOUT,
            conversation_id=conversation_id,
            originator_conversation_id=originator_id,
            result_desc='Daraja callback timeout',
            raw_payload=payload if isinstance(payload, dict) else {'payload': str(payload)},
        )

    logger.info("✅ Balance timeout recorded")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ==================== HELPER FUNCTIONS ====================

def _compute_defaulters_context(request):
    """
    Generate report of clients with outstanding vehicle balances.
    Source of truth: ClientVehicle.balance > 0 (not limited to clients with
    formal overdue PaymentSchedule records — that approach misses clients who
    owe money but have no installment plan or whose first scheduled payment has
    not yet been recorded as overdue).
    Shared by the on-screen defaulters report and its PDF/Excel/CSV exports.
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
    return context


@login_required
def defaulters_report_view(request):
    context = _compute_defaulters_context(request)
    log_audit(request.user, 'view', 'Payment', 'Viewed defaulters report')
    return render(request, 'payments/defaulters_report.html', context)


@login_required
def defaulters_report_export(request, fmt):
    """Export the Defaulters Report as PDF/Excel/CSV."""
    from utils.report_kit import export_rows
    ctx = _compute_defaulters_context(request)
    headers = ['Client', 'Phone', 'Vehicle', 'Days Overdue', 'Outstanding', 'Last Payment']
    rows = [
        [
            d['client'].get_full_name(), d['client'].phone_primary or '', d['vehicle'].full_name,
            d['days_overdue'], float(d['total_outstanding']),
            d['last_payment_date'].strftime('%Y-%m-%d') if d['last_payment_date'] else '',
        ]
        for d in ctx['defaulters']
    ]
    return export_rows(fmt, 'defaulters_report', 'Defaulters Report', headers, rows, currency_cols={5})


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


@login_required
def client_statement_pdf_view(request, client_pk):
    """Generate and download the client ledger statement PDF (same filters as the on-screen statement)."""
    from .utils import generate_client_statement_pdf
    from apps.clients.models import Client
    from apps.clients.utils import build_client_ledger

    client = get_object_or_404(Client, pk=client_pk)
    date_from = request.GET.get('date_from') or None
    date_to = request.GET.get('date_to') or None
    vehicle_pk = request.GET.get('vehicle') or None
    payment_method = request.GET.get('payment_method') or None

    rows, summary = build_client_ledger(
        client, date_from=date_from, date_to=date_to,
        vehicle_pk=vehicle_pk, payment_method=payment_method
    )

    log_audit(request.user, 'export', 'Client', f'Generated statement PDF for {client.get_full_name()}')

    return generate_client_statement_pdf(client, rows, summary)


@login_required
@module_permission_required('payments', AccessLevel.READ_WRITE)
def payment_reconciliation_create(request, payment_pk):
    """Request a reconciliation against a wrongly-posted client payment."""
    from .forms import PaymentReconciliationForm

    original = get_object_or_404(Payment, pk=payment_pk)

    if original.is_reversed:
        messages.error(request, 'This payment has already been reversed and cannot be reconciled again.')
        return redirect('clients:client_statement', client_pk=original.client_vehicle.client.pk)

    if request.method == 'POST':
        # original_payment is set on the instance before validation, since it's
        # excluded from the form fields but Reconciliation.clean() requires it to be set.
        form = PaymentReconciliationForm(request.POST, instance=Reconciliation(original_payment=original))
        if form.is_valid():
            reconciliation = form.save(commit=False)
            reconciliation.initiated_by = request.user
            try:
                reconciliation.full_clean()
            except DjangoValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
                return render(request, 'payments/payment_reconciliation_form.html', {'form': form, 'original': original})
            reconciliation.save()
            log_audit(
                request.user, 'create', 'Reconciliation',
                f'Requested reconciliation ({reconciliation.get_issue_type_display()}) on payment #{original.pk}'
            )
            messages.success(request, 'Reconciliation request submitted for approval.')
            return redirect('clients:client_statement', client_pk=original.client_vehicle.client.pk)
    else:
        form = PaymentReconciliationForm()

    return render(request, 'payments/payment_reconciliation_form.html', {'form': form, 'original': original})


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
    Returns JSON: { ok, status, paid, mpesa_receipt_number, result_desc,
                    payment_id, payment_url, receipt_url }

    A successful STK push is recorded automatically by the callback the
    moment Safaricom confirms it (see stk_push_callback) — the Payment
    already exists by the time this poll sees status='success'. Callers
    should link/redirect to payment_url rather than submitting the record
    form again, which would create a duplicate Payment for the same receipt.
    """
    checkout_request_id = request.GET.get('checkout_request_id', '').strip()
    if not checkout_request_id:
        return JsonResponse({'ok': False, 'error': 'checkout_request_id required.'}, status=400)
    try:
        stk_req = MpesaSTKRequest.objects.select_related('payment').get(
            checkout_request_id=checkout_request_id
        )
    except MpesaSTKRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Request not found.'}, status=404)

    payment = stk_req.payment
    return JsonResponse({
        'ok': True,
        'status': stk_req.status,
        'paid': stk_req.status == 'success',
        'mpesa_receipt_number': stk_req.mpesa_receipt_number or '',
        'result_desc': stk_req.result_desc or '',
        'payment_id': payment.pk if payment else None,
        'payment_url': reverse('payments:payment_detail', args=[payment.pk]) if payment else '',
        'receipt_url': reverse('payments:payment_receipt', args=[payment.pk]) if payment else '',
    })