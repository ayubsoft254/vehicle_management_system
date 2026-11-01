"""
Manual payment recording and reversal, with admin approval and duplicate
protection. Shared by record_payment, quick_record_payment, the payment
reversal view and the approval queue so every manual path follows the same
rules:

- Every manual payment is a PaymentRequest. A non-admin's request waits as
  pending and does not touch balances/ledgers until an admin approves it;
  an admin's own request is approved on submission.
- A transaction reference (M-Pesa code, bank ref, cheque no.) can back only
  one active payment. Checked against existing payments, payment splits,
  held proforma deposits and other requests, and enforced in the database
  by PaymentReferenceClaim's conditional unique constraint.
- Reversals are requested with a reason and applied by an admin.
"""
from apps.company.services import currency
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace, Upper
from django.urls import reverse
from django.utils import timezone

from utils.constants import UserRole

from .models import Payment, PaymentReferenceClaim, PaymentRequest, PaymentSplit

# Methods with no external transaction to quote. Everything else must carry
# its reference so the same transaction can't be entered twice.
NO_REFERENCE_METHODS = {'cash', 'other'}
METHOD_LABELS = dict(Payment.PAYMENT_METHOD_CHOICES)


class DuplicatePaymentError(ValueError):
    """Raised when a submission would record an already-recorded transaction."""


def is_payment_approver(user):
    """Admins approve manual payments and reversals."""
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN))


def normalize_reference(reference):
    """'qk1 2ab' and 'QK12AB' are the same M-Pesa code."""
    return ''.join((reference or '').split()).upper()


def reference_key(reference, method, client_id):
    """
    The uniqueness key for a reference. M-Pesa codes and bank references are
    globally unique; cheque numbers repeat across banks, so they are only
    treated as duplicates within the same client.
    """
    ref = normalize_reference(reference)
    if not ref:
        return ''
    if method == 'cheque':
        return f'CHQ:{client_id}:{ref}'
    return ref


def _normalized(field):
    return Upper(Replace(field, Value(' '), Value('')))


def find_reference_conflicts(portions, client_vehicle, exclude_request=None):
    """
    For each referenced portion, describe where that reference is already
    recorded. Returns a list of human-readable conflicts (empty = none).
    """
    from apps.clients.models import ProformaDeposit

    client_id = client_vehicle.client_id
    conflicts = []
    for method, _amount, reference, _location in portions:
        key = reference_key(reference, method, client_id)
        if not key:
            continue
        ref = normalize_reference(reference)
        cheque_scope = Q(client_vehicle__client_id=client_id) if method == 'cheque' else Q()

        payment = (
            Payment.objects.annotate(ref=_normalized('transaction_reference'))
            .filter(cheque_scope, ref=ref, is_reversed=False)
            .select_related('client_vehicle__client').first()
        )
        if payment:
            conflicts.append(
                f'Reference {ref} is already recorded on receipt {payment.receipt_number} '
                f'({payment.client_vehicle.client.get_full_name()}, {currency()} {payment.amount:,.2f}, '
                f'{payment.payment_date:%d %b %Y}).'
            )
            continue

        split_scope = Q(payment__client_vehicle__client_id=client_id) if method == 'cheque' else Q()
        split = (
            PaymentSplit.objects.annotate(ref=_normalized('transaction_reference'))
            .filter(split_scope, ref=ref, payment__is_reversed=False)
            .select_related('payment__client_vehicle__client').first()
        )
        if split:
            conflicts.append(
                f'Reference {ref} is already recorded on receipt {split.payment.receipt_number} '
                f'({split.payment.client_vehicle.client.get_full_name()}, split portion {currency()} {split.amount:,.2f}).'
            )
            continue

        deposit_scope = Q(proforma__client_id=client_id) if method == 'cheque' else Q()
        deposit = (
            ProformaDeposit.objects.annotate(ref=_normalized('transaction_reference'))
            .filter(deposit_scope, ref=ref, is_reversed=False, converted_payment__isnull=True)
            .select_related('proforma').first()
        )
        if deposit:
            conflicts.append(
                f'Reference {ref} is already held as a deposit on proforma {deposit.proforma.number}.'
            )
            continue

        claims = PaymentReferenceClaim.objects.filter(reference_key=key, is_active=True)
        if exclude_request is not None:
            claims = claims.exclude(payment_request=exclude_request)
        claim = claims.select_related('payment_request').first()
        if claim:
            other = claim.payment_request
            state = 'awaiting approval' if other.status == PaymentRequest.STATUS_PENDING else 'recorded'
            conflicts.append(f'Reference {ref} is already {state} (payment request #{other.pk}).')
    return conflicts


def find_possible_duplicate(client_vehicle, amount, payment_date, exclude_request=None):
    """
    For payments with no reference (cash), the best signal of a double entry
    is the same sale, amount and date. Returns a description or ''.
    """
    payment = Payment.objects.filter(
        client_vehicle=client_vehicle, amount=amount, payment_date=payment_date, is_reversed=False,
    ).first()
    if payment:
        return (f'Receipt {payment.receipt_number} already records {currency()} {amount:,.2f} '
                f'for this sale on {payment_date:%d %b %Y}.')
    pending = PaymentRequest.objects.filter(
        client_vehicle=client_vehicle, request_type=PaymentRequest.TYPE_RECORD,
        status=PaymentRequest.STATUS_PENDING, amount=amount, payment_date=payment_date,
    )
    if exclude_request is not None:
        pending = pending.exclude(pk=exclude_request.pk)
    pending = pending.first()
    if pending:
        return (f'Payment request #{pending.pk} for {currency()} {amount:,.2f} on {payment_date:%d %b %Y} '
                'is already awaiting approval for this sale.')
    return ''


def parse_manual_payment(post, client_vehicle):
    """
    Validate a submitted Record Payment form (single or split) into the
    fields of a PaymentRequest. Returns (data, errors); data is None when
    there are errors. A possible no-reference duplicate is reported in
    data['possible_duplicate'] for the caller to confirm.
    """
    errors = []
    today = timezone.localdate()

    payment_date = None
    date_raw = (post.get('payment_date') or '').strip()
    try:
        from datetime import date as _date
        payment_date = _date.fromisoformat(date_raw) if date_raw else today
    except ValueError:
        errors.append('Enter a valid payment date.')
    if payment_date:
        if payment_date > today:
            errors.append('Payment date cannot be in the future.')
        elif payment_date < today - timedelta(days=365):
            errors.append('Payment date cannot be more than 1 year in the past.')

    splits_in = [
        (m, a, r, loc) for m, a, r, loc in zip(
            post.getlist('split_method[]'), post.getlist('split_amount[]'),
            post.getlist('split_reference[]'), post.getlist('split_location[]'),
        ) if m and a
    ]
    is_split = len(splits_in) > 1
    raw_portions = splits_in if is_split else [(
        post.get('payment_method', ''), post.get('amount', ''),
        post.get('transaction_reference', ''), post.get('payment_location', ''),
    )]

    portions = []
    seen_keys = set()
    for index, (method, amount_raw, reference, location) in enumerate(raw_portions, start=1):
        label = f'Split {index}: ' if is_split else ''
        if method not in METHOD_LABELS or method == 'mixed':
            errors.append(f'{label}Choose a valid payment method.')
            continue
        try:
            amount = Decimal(str(amount_raw).replace(',', '').strip())
        except (InvalidOperation, ValueError):
            errors.append(f'{label}Enter a valid amount.')
            continue
        if amount <= 0:
            errors.append(f'{label}Amount must be greater than zero.')
            continue
        reference = (reference or '').strip()
        if method not in NO_REFERENCE_METHODS and not reference:
            errors.append(
                f'{label}A transaction reference is required for {METHOD_LABELS[method]} payments '
                '(M-Pesa code, bank reference or cheque number).'
            )
            continue
        key = reference_key(reference, method, client_vehicle.client_id)
        if key and key in seen_keys:
            errors.append(f'{label}Reference {normalize_reference(reference)} is entered more than once.')
            continue
        seen_keys.add(key)
        portions.append((method, amount.quantize(Decimal('0.01')), reference, (location or '').strip()))

    if errors:
        return None, errors

    conflicts = find_reference_conflicts(portions, client_vehicle)
    if conflicts:
        return None, conflicts

    total = sum((p[1] for p in portions), Decimal('0.00'))
    data = {
        'amount': total,
        'payment_date': payment_date,
        'payment_method': 'mixed' if is_split else portions[0][0],
        'transaction_reference': '' if is_split else portions[0][2],
        'payment_location': '' if is_split else portions[0][3],
        'notes': (post.get('notes') or '').strip(),
        'splits': [
            {'method': m, 'amount': str(a), 'reference': r, 'location': loc} for m, a, r, loc in portions
        ] if is_split else [],
        'possible_duplicate': '',
    }
    if not any(p[2] for p in portions):
        data['possible_duplicate'] = find_possible_duplicate(client_vehicle, total, payment_date)
    return data, []


def _claim_references(payment_request):
    """Reserve the request's references; the unique constraint rejects a reference already in use."""
    client_id = payment_request.client_vehicle.client_id
    for method, _amount, reference, _location in payment_request.portions():
        key = reference_key(reference, method, client_id)
        if key:
            PaymentReferenceClaim.objects.create(payment_request=payment_request, reference_key=key)


def _notify(users, title, message, url, priority='medium'):
    from apps.notifications.models import Notification
    for user in users:
        try:
            Notification.objects.create(
                user=user, title=title, message=message, notification_type='payment',
                action_url=url, priority=priority,
            )
        except Exception:
            # A notification must never block a payment decision
            pass


def _approvers():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(role=UserRole.ADMIN))


def submit_payment_request(user, client_vehicle, data):
    """
    Create a 'record' request from parse_manual_payment data. Admins' requests
    are approved immediately and the created Payment is returned with it.
    Returns (payment_request, payment_or_None).
    """
    with transaction.atomic():
        payment_request = PaymentRequest.objects.create(
            request_type=PaymentRequest.TYPE_RECORD,
            client_vehicle=client_vehicle,
            amount=data['amount'],
            payment_date=data['payment_date'],
            payment_method=data['payment_method'],
            transaction_reference=data['transaction_reference'],
            payment_location=data['payment_location'],
            notes=data['notes'],
            splits=data['splits'],
            possible_duplicate_note=data.get('possible_duplicate', ''),
            requested_by=user,
        )
        try:
            with transaction.atomic():
                _claim_references(payment_request)
        except IntegrityError:
            # Someone else claimed the same reference between our check and now
            raise DuplicatePaymentError(
                'This transaction reference was just recorded by someone else. Check Payment History.'
            )

        if is_payment_approver(user):
            payment = approve_payment_request(payment_request, user)
            return payment_request, payment

    _notify(
        _approvers(), 'Payment awaiting approval',
        f'{user.get_full_name() or user.email} recorded {currency()} {payment_request.amount:,.2f} for '
        f'{client_vehicle.client.get_full_name()} — approval needed.',
        reverse('payments:payment_request_list'), priority='high',
    )
    return payment_request, None


def submit_reversal_request(user, payment, reason):
    """Request (or, for an admin, perform) the reversal of a payment."""
    reason = (reason or '').strip()
    if payment.is_reversed:
        raise ValueError('This payment has already been reversed.')
    if not reason:
        raise ValueError('A reason is required to reverse a payment.')
    if PaymentRequest.objects.filter(
        payment=payment, request_type=PaymentRequest.TYPE_REVERSE, status=PaymentRequest.STATUS_PENDING,
    ).exists():
        raise ValueError('A reversal of this payment is already awaiting approval.')

    with transaction.atomic():
        try:
            with transaction.atomic():
                payment_request = PaymentRequest.objects.create(
                    request_type=PaymentRequest.TYPE_REVERSE,
                    client_vehicle=payment.client_vehicle,
                    payment=payment,
                    amount=payment.amount,
                    payment_date=payment.payment_date,
                    payment_method=payment.payment_method,
                    transaction_reference=payment.transaction_reference or '',
                    reason=reason,
                    requested_by=user,
                )
        except IntegrityError:
            raise ValueError('A reversal of this payment is already awaiting approval.')
        if is_payment_approver(user):
            approve_payment_request(payment_request, user)
            return payment_request

    _notify(
        _approvers(), 'Payment reversal awaiting approval',
        f'{user.get_full_name() or user.email} asked to reverse receipt {payment.receipt_number} '
        f'({currency()} {payment.amount:,.2f}): {reason}',
        reverse('payments:payment_request_list'), priority='high',
    )
    return payment_request


def approve_payment_request(payment_request, user, note=''):
    """
    Apply a pending request. 'record' creates the Payment (signals then
    update the balance, schedules and ledgers); 'reverse' reverses it.
    Duplicate checks are re-run at approval time against everything recorded
    since submission. Returns the Payment.
    """
    if not is_payment_approver(user):
        raise PermissionError('Only an administrator can approve payment requests.')

    with transaction.atomic():
        payment_request = PaymentRequest.objects.select_for_update().get(pk=payment_request.pk)
        if payment_request.status != PaymentRequest.STATUS_PENDING:
            raise ValueError(f'This request has already been {payment_request.get_status_display().lower()}.')

        if payment_request.request_type == PaymentRequest.TYPE_RECORD:
            conflicts = find_reference_conflicts(
                payment_request.portions(), payment_request.client_vehicle, exclude_request=payment_request,
            )
            if conflicts:
                raise DuplicatePaymentError(' '.join(conflicts))

            payment = Payment.objects.create(
                client_vehicle=payment_request.client_vehicle,
                amount=payment_request.amount,
                payment_date=payment_request.payment_date,
                payment_method=payment_request.payment_method,
                transaction_reference=payment_request.transaction_reference or None,
                payment_location=payment_request.payment_location or None,
                notes=payment_request.notes,
                recorded_by=payment_request.requested_by,
            )
            for method, amount, reference, location in (payment_request.portions() if payment_request.is_split else []):
                PaymentSplit.objects.create(
                    payment=payment, payment_method=method, amount=amount,
                    transaction_reference=reference or None, payment_location=location or None,
                )
            payment_request.payment = payment
        else:
            payment = payment_request.payment
            if payment is None:
                raise ValueError('The payment for this reversal no longer exists.')
            requester = payment_request.requested_by
            reason = payment_request.reason
            if requester and requester != user:
                reason = f'{reason} (requested by {requester.get_full_name() or requester.email})'
            payment.reverse_payment(user=user, reason=reason)

        payment_request.status = PaymentRequest.STATUS_APPROVED
        payment_request.reviewed_by = user
        payment_request.reviewed_at = timezone.now()
        payment_request.review_note = note
        payment_request.save()

    if payment_request.requested_by and payment_request.requested_by != user:
        what = 'Payment' if payment_request.request_type == PaymentRequest.TYPE_RECORD else 'Reversal'
        _notify(
            [payment_request.requested_by], f'{what} approved',
            f'Your {payment_request.get_request_type_display().lower()} request #{payment_request.pk} '
            f'({currency()} {payment_request.amount:,.2f}) was approved.',
            reverse('payments:payment_detail', args=[payment.pk]),
        )
    return payment


def reject_payment_request(payment_request, user, note=''):
    """Reject a pending request and release its references."""
    if not is_payment_approver(user):
        raise PermissionError('Only an administrator can reject payment requests.')
    with transaction.atomic():
        payment_request = PaymentRequest.objects.select_for_update().get(pk=payment_request.pk)
        if payment_request.status != PaymentRequest.STATUS_PENDING:
            raise ValueError(f'This request has already been {payment_request.get_status_display().lower()}.')
        payment_request.status = PaymentRequest.STATUS_REJECTED
        payment_request.reviewed_by = user
        payment_request.reviewed_at = timezone.now()
        payment_request.review_note = note
        payment_request.save()
        payment_request.reference_claims.update(is_active=False)

    if payment_request.requested_by and payment_request.requested_by != user:
        _notify(
            [payment_request.requested_by], 'Payment request rejected',
            f'Your {payment_request.get_request_type_display().lower()} request #{payment_request.pk} '
            f'({currency()} {payment_request.amount:,.2f}) was rejected{": " + note if note else "."}',
            reverse('payments:payment_request_list'),
        )
    return payment_request
