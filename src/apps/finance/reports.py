"""
Report query helpers for the finance app.

Most of the spec's 16 report types collapse into "the ledger, filtered a
particular way" (client payments, expenses, vendor payments, transfers,
pending/rejected/reversed/corrected, vehicle payments, ...) — rather than
16 near-duplicate views, filter_transactions() implements that filtering
once and finance/views.py exposes it through one flexible Reports page
plus CSV export. period_summary() covers the daily/monthly/yearly
financial summary reports separately, since those aggregate rather than list.
"""
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncYear

from .models import LedgerTransaction

REPORT_TYPES = [
    ('all', 'All Transactions (Account Ledger / Statement)'),
    ('client_payments', 'Client Payment Report'),
    ('expenses', 'Expense Report'),
    ('vendor_payments', 'Supplier/Vendor Payment Report'),
    ('transfers', 'Internal Transfer Report'),
    ('pending', 'Pending Approval Report'),
    ('rejected', 'Rejected Transaction Report'),
    ('reversed', 'Reversed Transaction Report'),
    ('corrected', 'Corrected Transaction Report'),
    ('vehicle_payments', 'Vehicle Payment Report'),
]

PERIOD_CHOICES = [
    ('daily', 'Daily'),
    ('monthly', 'Monthly'),
    ('yearly', 'Yearly'),
]

_REPORT_TYPE_FILTERS = {
    'client_payments': lambda qs: qs.filter(source_module='payments', direction='credit'),
    'expenses': lambda qs: qs.filter(source_module='expenses'),
    'vendor_payments': lambda qs: qs.filter(source_module__in=['vehicles', 'insurance'], direction='debit'),
    'transfers': lambda qs: qs.filter(source_module='transfer'),
    'pending': lambda qs: qs.filter(status='pending_approval'),
    'rejected': lambda qs: qs.filter(status='rejected'),
    'reversed': lambda qs: qs.filter(Q(status='reversed') | Q(is_reversal=True)),
    'corrected': lambda qs: qs.filter(is_correction=True),
    'vehicle_payments': lambda qs: qs.filter(related_vehicle__isnull=False),
}


def filter_transactions(report_type='all', *, account=None, date_from=None, date_to=None,
                         transaction_type=None, status=None, client=None, vehicle=None, search=None):
    qs = LedgerTransaction.objects.select_related(
        'account', 'related_client', 'related_vehicle', 'created_by', 'approved_by'
    )

    type_filter = _REPORT_TYPE_FILTERS.get(report_type)
    if type_filter:
        qs = type_filter(qs)

    if account:
        qs = qs.filter(account=account)
    if date_from:
        qs = qs.filter(transaction_date__gte=date_from)
    if date_to:
        qs = qs.filter(transaction_date__lte=date_to)
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    if status:
        qs = qs.filter(status=status)
    if client:
        qs = qs.filter(related_client=client)
    if vehicle:
        qs = qs.filter(related_vehicle=vehicle)
    if search:
        qs = qs.filter(
            Q(reference_number__icontains=search) | Q(description__icontains=search)
            | Q(related_party_label__icontains=search)
        )

    return qs.order_by('-transaction_date', '-created_at')


def summarize(qs):
    """Approved-balance-relevant totals for a filtered queryset (mirrors the account balance rule)."""
    approved = qs.filter(status__in=['approved', 'reversed'])
    credits = approved.filter(direction='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    debits = approved.filter(direction='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    return {
        'count': qs.count(),
        'total_credits': credits,
        'total_debits': debits,
        'net': credits - debits,
    }


_TRUNC_FUNCS = {'daily': TruncDate, 'monthly': TruncMonth, 'yearly': TruncYear}


def period_summary(period='monthly', *, account=None, date_from=None, date_to=None):
    """Daily/monthly/yearly financial summary: approved credits/debits grouped by period."""
    trunc_fn = _TRUNC_FUNCS.get(period, TruncMonth)

    qs = LedgerTransaction.objects.filter(status__in=['approved', 'reversed'])
    if account:
        qs = qs.filter(account=account)
    if date_from:
        qs = qs.filter(transaction_date__gte=date_from)
    if date_to:
        qs = qs.filter(transaction_date__lte=date_to)

    grouped = qs.annotate(period=trunc_fn('transaction_date')).values('period').annotate(
        credits=Sum('amount', filter=Q(direction='credit')),
        debits=Sum('amount', filter=Q(direction='debit')),
    ).order_by('-period')

    rows = []
    for row in grouped:
        credits = row['credits'] or Decimal('0.00')
        debits = row['debits'] or Decimal('0.00')
        rows.append({'period': row['period'], 'credits': credits, 'debits': debits, 'net': credits - debits})
    return rows
