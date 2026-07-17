"""
Shared helpers for building a client's financial ledger.
Used by the HTML statement view and the CSV/Excel/PDF exports so all four
always show identical numbers - the ledger is computed from Payment/
ClientVehicle, never stored separately.
"""
from decimal import Decimal
from django.urls import reverse

from .models import ClientVehicle, ProformaDeposit
from apps.payments.models import Payment

ZERO = Decimal('0.00')

SALE_TYPE_LABELS = {
    'full': 'Cash Sale',
    'installment': 'Hire Purchase',
    'flexible': 'Hire Purchase (Flexible)',
}


def build_client_ledger(client, date_from=None, date_to=None, vehicle_pk=None, payment_method=None):
    """
    Returns (rows, summary) for a client's financial ledger.

    rows: chronological list of dicts (debit = vehicle purchase, credit =
    payment), each with a running balance.
    summary: aggregate totals, per-vehicle breakdown, and overpayment.
    """
    client_vehicles = ClientVehicle.objects.filter(client=client).select_related('vehicle')
    if vehicle_pk:
        client_vehicles = client_vehicles.filter(pk=vehicle_pk)

    payments = Payment.objects.filter(client_vehicle__client=client).select_related(
        'client_vehicle__vehicle', 'recorded_by'
    ).prefetch_related('splits', 'reconciliations')
    if vehicle_pk:
        payments = payments.filter(client_vehicle__pk=vehicle_pk)
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)

    rows = []

    for cv in client_vehicles:
        if date_from and cv.purchase_date < date_from:
            continue
        if date_to and cv.purchase_date > date_to:
            continue
        rows.append({
            'date': cv.purchase_date,
            'sort_key': cv.purchase_date.toordinal(),
            'reference': f'CV-{cv.pk}',
            'type_label': 'Vehicle Purchase',
            'payment_method': '',
            'narration': f'{cv.vehicle.full_name} ({SALE_TYPE_LABELS.get(cv.payment_type, cv.payment_type)})',
            'related_vehicle': cv.vehicle,
            'debit': cv.purchase_price,
            'credit': ZERO,
            'created_by': None,
            'reconciliation_status': '—',
            'notes': '',
            'detail_url': reverse('clients:client_vehicle_detail', args=[cv.pk]),
            'is_reversed': False,
            'payment_pk': None,
            'can_reconcile': False,
        })

    for payment in payments:
        latest_reconciliation = payment.reconciliations.order_by('-created_at').first()
        if payment.splits.exists():
            portions = [(split.payment_method, split.amount, split.transaction_reference) for split in payment.splits.all()]
        else:
            portions = [(payment.payment_method, payment.amount, payment.transaction_reference)]

        if payment_method and not any(m == payment_method for m, _a, _r in portions):
            continue

        for method, amount, ref in portions:
            rows.append({
                'date': payment.payment_date,
                'sort_key': payment.created_at.timestamp(),
                'reference': ref or payment.receipt_number,
                'type_label': 'Payment',
                'payment_method': dict(Payment.PAYMENT_METHOD_CHOICES).get(method, method),
                'narration': payment.notes or '',
                'related_vehicle': payment.client_vehicle.vehicle,
                'debit': ZERO,
                'credit': ZERO if payment.is_reversed else amount,
                'display_amount': amount,
                'created_by': payment.recorded_by,
                'reconciliation_status': latest_reconciliation.get_status_display() if latest_reconciliation else '—',
                'notes': payment.notes or '',
                'detail_url': reverse('payments:payment_detail', args=[payment.pk]),
                'is_reversed': payment.is_reversed,
                'payment_pk': payment.pk,
                'can_reconcile': not payment.is_reversed,
            })

    # Commitment deposits held against proforma invoices that have not yet
    # converted into a sale. Once converted, the deposit shows through the
    # Payment created at conversion time — never both (no double counting).
    held_deposits = ProformaDeposit.objects.filter(
        proforma__client=client,
        is_reversed=False,
        converted_payment__isnull=True,
    ).select_related('proforma__vehicle', 'confirmed_by')
    if vehicle_pk:
        # Proforma deposits are tied to a vehicle, not a ClientVehicle;
        # skip them entirely when a specific purchase is being filtered.
        held_deposits = held_deposits.none()
    if date_from:
        held_deposits = held_deposits.filter(payment_date__gte=date_from)
    if date_to:
        held_deposits = held_deposits.filter(payment_date__lte=date_to)

    deposits_held_total = ZERO
    for deposit in held_deposits:
        if payment_method and deposit.payment_method != payment_method:
            continue
        deposits_held_total += deposit.amount
        rows.append({
            'date': deposit.payment_date,
            'sort_key': deposit.confirmed_at.timestamp(),
            'reference': deposit.transaction_reference or deposit.proforma.number,
            'type_label': 'Proforma Deposit',
            'payment_method': deposit.get_payment_method_display(),
            'narration': f'Commitment deposit held — {deposit.proforma.number} ({deposit.proforma.vehicle.full_name})',
            'related_vehicle': deposit.proforma.vehicle,
            'debit': ZERO,
            'credit': deposit.amount,
            'display_amount': deposit.amount,
            'created_by': deposit.confirmed_by,
            'reconciliation_status': '—',
            'notes': deposit.notes or '',
            'detail_url': reverse('clients:proforma_detail', args=[deposit.proforma.pk]),
            'is_reversed': False,
            'payment_pk': None,
            'can_reconcile': False,
        })

    rows.sort(key=lambda r: (r['date'], r['sort_key']))
    running = ZERO
    for row in rows:
        running += row['debit'] - row['credit']
        row['running_balance'] = running
    rows.reverse()

    total_expected = sum((cv.purchase_price for cv in client_vehicles), ZERO)
    total_paid = sum((cv.total_paid for cv in client_vehicles), ZERO)
    outstanding = sum((cv.balance for cv in client_vehicles), ZERO)
    overpayment = sum((max(ZERO, cv.total_paid - cv.purchase_price) for cv in client_vehicles), ZERO)

    vehicles_summary = [
        {
            'client_vehicle': cv,
            'sale_type': SALE_TYPE_LABELS.get(cv.payment_type, cv.payment_type),
            'is_paid_off': cv.is_paid_off,
            'overpayment': max(ZERO, cv.total_paid - cv.purchase_price),
        }
        for cv in client_vehicles
    ]

    if outstanding > 0:
        payment_status = 'Outstanding Balance'
    elif overpayment > 0:
        payment_status = 'Overpaid'
    else:
        payment_status = 'Fully Paid'

    summary = {
        'total_expected': total_expected,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'overpayment': overpayment,
        'deposits_held': deposits_held_total,
        'payment_status': payment_status,
        'vehicles': vehicles_summary,
    }

    return rows, summary
