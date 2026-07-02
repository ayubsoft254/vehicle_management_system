"""
Business logic for creating and moving LedgerTransaction records through
their approval lifecycle. Centralized here so Phase 3/4 integrations
(client payments, expenses, vendor payments, ...) can create ledger
entries the same way the manual entry views in this app do.
"""
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    InternalTransfer, LedgerTransaction, SuspenseTransaction,
    TransactionApproval, TransactionAuditTrail,
)


def _log_approval_action(ledger_transaction, action, actioned_by, comments=''):
    TransactionApproval.objects.create(
        transaction=ledger_transaction, action=action, actioned_by=actioned_by, comments=comments
    )


def _log_audit(ledger_transaction, action, changed_by, old_values=None, new_values=None,
                ip_address=None, user_agent=''):
    TransactionAuditTrail.objects.create(
        transaction=ledger_transaction, action=action, changed_by=changed_by,
        old_values=old_values, new_values=new_values,
        ip_address=ip_address, user_agent=user_agent,
    )


@db_transaction.atomic
def create_transaction(account, *, direction, transaction_type, amount, created_by, force_pending=False, **fields):
    """
    Create a LedgerTransaction on `account`.

    Status is decided by the account's require_approval flag: accounts that
    don't require approval post straight to 'approved', everything else
    starts 'pending_approval' and needs a separate approve_transaction() call.
    Pass force_pending=True to require approval regardless of the account's
    own flag (used for internal transfers, where either leg can force both).
    """
    auto_approved = not account.require_approval and not force_pending

    ledger_transaction = LedgerTransaction.objects.create(
        account=account,
        direction=direction,
        transaction_type=transaction_type,
        amount=amount,
        created_by=created_by,
        status='approved' if auto_approved else 'pending_approval',
        approved_by=created_by if auto_approved else None,
        approved_at=timezone.now() if auto_approved else None,
        **fields,
    )

    _log_approval_action(ledger_transaction, 'submitted', created_by)
    _log_audit(ledger_transaction, 'create', created_by, new_values={
        'amount': str(amount), 'direction': direction, 'transaction_type': transaction_type,
    })
    if auto_approved:
        _log_approval_action(ledger_transaction, 'approved', created_by, comments='Auto-approved: account does not require approval')
        _log_audit(ledger_transaction, 'approve', created_by)

    # Credits landing in a suspense account are, by definition, unmatched —
    # track them for allocation. Debits out of suspense (e.g. moving funds
    # elsewhere once identified) don't need this.
    if account.account_type == 'suspense' and direction == 'credit':
        SuspenseTransaction.objects.create(transaction=ledger_transaction)

    return ledger_transaction


@db_transaction.atomic
def approve_transaction(ledger_transaction, user, comments='', ip_address=None, user_agent=''):
    if ledger_transaction.status != 'pending_approval':
        raise ValueError('Only transactions pending approval can be approved.')
    if ledger_transaction.created_by_id == user.id and not user.is_superuser:
        raise PermissionError('You cannot approve a transaction you created yourself.')

    ledger_transaction.status = 'approved'
    ledger_transaction.approved_by = user
    ledger_transaction.approved_at = timezone.now()
    ledger_transaction.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    _log_approval_action(ledger_transaction, 'approved', user, comments)
    _log_audit(ledger_transaction, 'approve', user, ip_address=ip_address, user_agent=user_agent)
    return ledger_transaction


@db_transaction.atomic
def reject_transaction(ledger_transaction, user, comments='', ip_address=None, user_agent=''):
    if ledger_transaction.status != 'pending_approval':
        raise ValueError('Only transactions pending approval can be rejected.')

    ledger_transaction.status = 'rejected'
    ledger_transaction.save(update_fields=['status', 'updated_at'])

    _log_approval_action(ledger_transaction, 'rejected', user, comments)
    _log_audit(ledger_transaction, 'reject', user, ip_address=ip_address, user_agent=user_agent)
    return ledger_transaction


@db_transaction.atomic
def request_transaction_edit(ledger_transaction, user, comments, ip_address=None, user_agent=''):
    """An approver sends a pending transaction back to its creator for correction."""
    if ledger_transaction.status != 'pending_approval':
        raise ValueError('Only transactions pending approval can have an edit requested.')
    if not comments:
        raise ValueError('A reason is required when requesting an edit.')

    ledger_transaction.status = 'edit_requested'
    ledger_transaction.save(update_fields=['status', 'updated_at'])

    _log_approval_action(ledger_transaction, 'edit_requested', user, comments)
    _log_audit(ledger_transaction, 'update', user, ip_address=ip_address, user_agent=user_agent)
    return ledger_transaction


# Fields callers may update via edit_transaction(); intentionally excludes
# account/direction/amount identity fields that would change what the
# transaction fundamentally represents — those require reverse+correct instead.
EDITABLE_TRANSACTION_FIELDS = [
    'transaction_date', 'transaction_type', 'amount', 'currency',
    'related_client', 'related_vehicle', 'related_party_label',
    'payment_method', 'description', 'supporting_document',
]


@db_transaction.atomic
def edit_transaction(ledger_transaction, user, reason, ip_address=None, user_agent='', **field_updates):
    """
    Edit a transaction that has not been approved yet (draft/pending_approval/
    edit_requested). Approved transactions must go through reverse_transaction()
    / correct_transaction() instead — this never touches an approved record.
    """
    if ledger_transaction.status not in ('draft', 'pending_approval', 'edit_requested'):
        raise ValueError('Only draft, pending, or edit-requested transactions can be edited.')
    if not reason:
        raise ValueError('A reason is required when editing a transaction.')

    unknown_fields = set(field_updates) - set(EDITABLE_TRANSACTION_FIELDS)
    if unknown_fields:
        raise ValueError(f'Cannot edit field(s): {", ".join(sorted(unknown_fields))}')

    old_values = {}
    new_values = {}
    for field, new_value in field_updates.items():
        old_value = getattr(ledger_transaction, field)
        # Normalize falsy-but-different representations (e.g. an empty
        # FieldFile vs None) so untouched file fields don't show as "changed".
        if (old_value or None) != (new_value or None):
            old_values[field] = str(old_value) if old_value else None
            new_values[field] = str(new_value) if new_value else None
            setattr(ledger_transaction, field, new_value)

    ledger_transaction.edit_reason = reason
    account = ledger_transaction.account
    auto_approved = not account.require_approval
    ledger_transaction.status = 'approved' if auto_approved else 'pending_approval'
    if auto_approved:
        ledger_transaction.approved_by = user
        ledger_transaction.approved_at = timezone.now()
    ledger_transaction.save()

    _log_approval_action(ledger_transaction, 'submitted', user, comments=f'Edited: {reason}')
    _log_audit(
        ledger_transaction, 'update', user,
        old_values=old_values, new_values=new_values,
        ip_address=ip_address, user_agent=user_agent,
    )
    return ledger_transaction


@db_transaction.atomic
def reverse_transaction(ledger_transaction, user, reason, ip_address=None, user_agent=''):
    """
    Reverse an approved transaction: creates an opposite-direction entry
    linked back to the original and marks the original 'reversed'. Never
    edits or deletes the original record.
    """
    if ledger_transaction.status != 'approved':
        raise ValueError('Only approved transactions can be reversed.')
    if ledger_transaction.is_reversal:
        raise ValueError('A reversal entry cannot itself be reversed; reverse/correct the original transaction.')
    if not reason:
        raise ValueError('A reason is required when reversing a transaction.')

    reversal = LedgerTransaction.objects.create(
        account=ledger_transaction.account,
        transaction_date=timezone.now().date(),
        direction='credit' if ledger_transaction.direction == 'debit' else 'debit',
        transaction_type='reversal',
        amount=ledger_transaction.amount,
        currency=ledger_transaction.currency,
        source_module=ledger_transaction.source_module,
        related_client=ledger_transaction.related_client,
        related_vehicle=ledger_transaction.related_vehicle,
        related_party_content_type=ledger_transaction.related_party_content_type,
        related_party_object_id=ledger_transaction.related_party_object_id,
        related_party_label=ledger_transaction.related_party_label,
        payment_method=ledger_transaction.payment_method,
        description=f'Reversal of {ledger_transaction.reference_number}: {reason}',
        status='approved',
        created_by=user,
        approved_by=user,
        approved_at=timezone.now(),
        is_reversal=True,
        original_transaction=ledger_transaction,
        reversal_reason=reason,
    )

    ledger_transaction.status = 'reversed'
    ledger_transaction.reversal_reason = reason
    ledger_transaction.save(update_fields=['status', 'reversal_reason', 'updated_at'])

    _log_approval_action(reversal, 'submitted', user, comments=f'Reversal: {reason}')
    _log_approval_action(reversal, 'approved', user, comments='Reversals post immediately')
    _log_audit(reversal, 'create', user, ip_address=ip_address, user_agent=user_agent)
    _log_audit(ledger_transaction, 'reverse', user, ip_address=ip_address, user_agent=user_agent)
    return reversal


@db_transaction.atomic
def correct_transaction(ledger_transaction, user, correct_amount, reason, ip_address=None, user_agent=''):
    """
    Fix a wrongly-recorded approved transaction: reverse the original, then
    post a new correct entry linked back to it. Both steps are atomic —
    either both happen or neither does.
    """
    if not reason:
        raise ValueError('A reason is required when correcting a transaction.')

    reversal = reverse_transaction(ledger_transaction, user, reason, ip_address=ip_address, user_agent=user_agent)

    corrected = LedgerTransaction.objects.create(
        account=ledger_transaction.account,
        transaction_date=timezone.now().date(),
        direction=ledger_transaction.direction,
        transaction_type=ledger_transaction.transaction_type,
        amount=correct_amount,
        currency=ledger_transaction.currency,
        source_module=ledger_transaction.source_module,
        related_client=ledger_transaction.related_client,
        related_vehicle=ledger_transaction.related_vehicle,
        related_party_content_type=ledger_transaction.related_party_content_type,
        related_party_object_id=ledger_transaction.related_party_object_id,
        related_party_label=ledger_transaction.related_party_label,
        payment_method=ledger_transaction.payment_method,
        description=f'Correction of {ledger_transaction.reference_number}: {reason}',
        status='approved',
        created_by=user,
        approved_by=user,
        approved_at=timezone.now(),
        is_correction=True,
        original_transaction=ledger_transaction,
        correction_reason=reason,
    )

    _log_approval_action(corrected, 'submitted', user, comments=f'Correction: {reason}')
    _log_approval_action(corrected, 'approved', user, comments='Corrections post immediately')
    _log_audit(corrected, 'create', user, ip_address=ip_address, user_agent=user_agent)
    _log_audit(ledger_transaction, 'correct', user, ip_address=ip_address, user_agent=user_agent)
    return reversal, corrected


@db_transaction.atomic
def create_internal_transfer(*, from_account, to_account, amount, created_by, transfer_date=None, notes=''):
    """Create the linked debit/credit LedgerTransaction pair for a transfer between accounts."""
    if from_account.pk == to_account.pk:
        raise ValueError('Cannot transfer an account to itself.')

    transfer_date = transfer_date or timezone.now().date()
    requires_approval = from_account.require_approval or to_account.require_approval

    transfer = InternalTransfer.objects.create(
        from_account=from_account, to_account=to_account, amount=amount,
        transfer_date=transfer_date, notes=notes, created_by=created_by,
        status='pending_approval' if requires_approval else 'approved',
    )

    shared_description = f'Internal transfer {transfer.transfer_reference}: {from_account.name} -> {to_account.name}'

    debit_txn = create_transaction(
        from_account, direction='debit', transaction_type='internal_transfer_sent', amount=amount,
        created_by=created_by, transaction_date=transfer_date, source_module='transfer',
        description=notes or shared_description, payment_method='internal_transfer',
        force_pending=requires_approval,
    )
    credit_txn = create_transaction(
        to_account, direction='credit', transaction_type='internal_transfer_received', amount=amount,
        created_by=created_by, transaction_date=transfer_date, source_module='transfer',
        description=notes or shared_description, payment_method='internal_transfer',
        force_pending=requires_approval,
    )

    transfer.debit_transaction = debit_txn
    transfer.credit_transaction = credit_txn
    transfer.save(update_fields=['debit_transaction', 'credit_transaction'])
    return transfer


@db_transaction.atomic
def approve_internal_transfer(transfer, user, comments=''):
    if transfer.status != 'pending_approval':
        raise ValueError('Only transfers pending approval can be approved.')

    for txn in (transfer.debit_transaction, transfer.credit_transaction):
        if txn and txn.status == 'pending_approval':
            approve_transaction(txn, user, comments)

    transfer.status = 'approved'
    transfer.approved_by = user
    transfer.approved_at = timezone.now()
    transfer.save(update_fields=['status', 'approved_by', 'approved_at'])
    return transfer


@db_transaction.atomic
def reject_internal_transfer(transfer, user, comments=''):
    if transfer.status != 'pending_approval':
        raise ValueError('Only transfers pending approval can be rejected.')

    for txn in (transfer.debit_transaction, transfer.credit_transaction):
        if txn and txn.status == 'pending_approval':
            reject_transaction(txn, user, comments)

    transfer.status = 'rejected'
    transfer.save(update_fields=['status'])
    return transfer


@db_transaction.atomic
def allocate_suspense_transaction(suspense_txn, user, *, client=None, client_vehicle=None,
                                   notes='', ip_address=None, user_agent=''):
    """
    Identify who an unmatched suspense payment actually belongs to. Tags the
    underlying LedgerTransaction with the client/vehicle (metadata only — the
    amount/account/direction are untouched, so this doesn't need the
    reverse+correct machinery) and marks the SuspenseTransaction resolved.
    """
    if suspense_txn.is_allocated:
        raise ValueError('This payment has already been allocated.')
    if not client and not client_vehicle:
        raise ValueError('Select a client or a vehicle to allocate this payment to.')

    ledger_transaction = suspense_txn.transaction
    old_values = {
        'related_client': str(ledger_transaction.related_client) if ledger_transaction.related_client else None,
        'related_vehicle': str(ledger_transaction.related_vehicle) if ledger_transaction.related_vehicle else None,
    }

    if client_vehicle:
        ledger_transaction.related_vehicle = client_vehicle.vehicle
        ledger_transaction.related_client = client or client_vehicle.client
    elif client:
        ledger_transaction.related_client = client
    ledger_transaction.save(update_fields=['related_client', 'related_vehicle', 'updated_at'])

    suspense_txn.is_allocated = True
    suspense_txn.allocated_by = user
    suspense_txn.allocated_at = timezone.now()
    suspense_txn.allocation_notes = notes
    suspense_txn.allocated_to = client_vehicle or client
    suspense_txn.save()

    new_values = {
        'related_client': str(ledger_transaction.related_client) if ledger_transaction.related_client else None,
        'related_vehicle': str(ledger_transaction.related_vehicle) if ledger_transaction.related_vehicle else None,
    }
    _log_audit(
        ledger_transaction, 'update', user,
        old_values=old_values, new_values=new_values,
        ip_address=ip_address, user_agent=user_agent,
    )
    return suspense_txn


@db_transaction.atomic
def complete_reconciliation(reconciliation, user):
    if reconciliation.status == 'completed':
        raise ValueError('This reconciliation is already completed.')
    reconciliation.status = 'completed'
    reconciliation.reconciled_by = user
    reconciliation.reconciled_at = timezone.now()
    reconciliation.save(update_fields=['status', 'reconciled_by', 'reconciled_at'])
    return reconciliation
