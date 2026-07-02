"""
Views for the finance app.
Phase 1: account management and a dashboard/ledger skeleton.
Phase 2: manual transaction entry, internal transfers, and a basic
approve/reject workflow.
Phase 5: edit requests, reversals, corrections, self-approval restriction,
and audit trail metadata (IP/user-agent).
Phase 6: reconciliation, suspense allocation, and reports.
"""
import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.utils import log_audit
from apps.permissions.models import RolePermission
from utils.constants import ModuleName

from . import reports as finance_reports
from . import services
from .forms import (
    AccountReconciliationForm, FinancialAccountForm, InternalTransferForm,
    LedgerTransactionEditForm, LedgerTransactionForm, SuspenseAllocationForm,
    TransactionCorrectionForm, TransactionReversalForm,
)
from .models import (
    AccountReconciliation, FinancialAccount, InternalTransfer,
    LedgerTransaction, SuspenseTransaction,
)


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def finance_access_required(view_func):
    """Restrict a view to users with any access level on the Finance module."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not (
            request.user.is_superuser
            or RolePermission.user_can_access_module(request.user, ModuleName.FINANCE)
        ):
            messages.error(request, "You don't have permission to access the Finance module.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _finance_permission(user):
    try:
        return RolePermission.objects.get(
            role=user.role, module_name=ModuleName.FINANCE, is_active=True
        )
    except RolePermission.DoesNotExist:
        return None


def _can_modify_finance(user):
    """Can manage accounts (add/edit/activate). Deliberately stricter than recording a transaction."""
    if user.is_superuser:
        return True
    permission = _finance_permission(user)
    return bool(permission and permission.can_edit)


def _can_record_transactions(user):
    """Can record new transactions/transfers (e.g. a cashier), without necessarily being able to approve them."""
    if user.is_superuser:
        return True
    permission = _finance_permission(user)
    return bool(permission and (permission.can_create or permission.can_edit))


def _can_approve_transactions(user):
    if user.is_superuser:
        return True
    permission = _finance_permission(user)
    return bool(permission and permission.can_edit)


def _can_reverse_transactions(user):
    """
    Reversals/corrections rewrite financial history (via linked entries, never
    in place) and are restricted to Super Admin by default — mapped onto the
    existing can_delete flag, the most restrictive one available, rather than
    inventing a new permission dimension. Give a role can_delete on the
    FINANCE module to extend this beyond superusers.
    """
    if user.is_superuser:
        return True
    permission = _finance_permission(user)
    return bool(permission and permission.can_delete)


def _can_export_finance(user):
    if user.is_superuser:
        return True
    permission = _finance_permission(user)
    return bool(permission and permission.can_export)


# ==================== DASHBOARD ====================

@finance_access_required
def finance_dashboard(request):
    accounts = FinancialAccount.objects.all()

    total_bank_balance = sum(
        (a.current_balance for a in accounts if a.account_type == 'bank'), start=0
    )
    total_cash_balance = sum(
        (a.current_balance for a in accounts if a.account_type == 'cash'), start=0
    )
    total_mpesa_balance = sum(
        (a.current_balance for a in accounts if a.account_type in ('mpesa_paybill', 'mpesa_till')),
        start=0
    )
    total_pending_inflows = sum((a.pending_inflows for a in accounts), start=0)
    total_pending_outflows = sum((a.pending_outflows for a in accounts), start=0)
    total_approved_credits = sum((a.approved_credits for a in accounts), start=0)
    total_approved_debits = sum((a.approved_debits for a in accounts), start=0)
    pending_approval_count = sum(
        (a.ledger_transactions.filter(status='pending_approval').count() for a in accounts), start=0
    )

    context = {
        'accounts': accounts,
        'total_bank_balance': total_bank_balance,
        'total_cash_balance': total_cash_balance,
        'total_mpesa_balance': total_mpesa_balance,
        'total_pending_inflows': total_pending_inflows,
        'total_pending_outflows': total_pending_outflows,
        'total_approved_credits': total_approved_credits,
        'total_approved_debits': total_approved_debits,
        'pending_approval_count': pending_approval_count,
        'can_modify': _can_modify_finance(request.user),
        'can_record': _can_record_transactions(request.user),
    }
    return render(request, 'finance/dashboard.html', context)


# ==================== ACCOUNT MANAGEMENT ====================

@finance_access_required
def account_list(request):
    accounts = FinancialAccount.objects.all()

    query = request.GET.get('q', '').strip()
    if query:
        accounts = accounts.filter(
            Q(name__icontains=query) | Q(code__icontains=query)
            | Q(bank_name__icontains=query) | Q(account_number__icontains=query)
        )

    account_type = request.GET.get('account_type', '')
    if account_type:
        accounts = accounts.filter(account_type=account_type)

    status = request.GET.get('status', '')
    if status:
        accounts = accounts.filter(status=status)

    paginator = Paginator(accounts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'accounts': page_obj.object_list,
        'account_types': FinancialAccount.ACCOUNT_TYPE_CHOICES,
        'query': query,
        'selected_account_type': account_type,
        'selected_status': status,
        'can_modify': _can_modify_finance(request.user),
        'can_record': _can_record_transactions(request.user),
    }
    return render(request, 'finance/account_list.html', context)


@finance_access_required
def account_add(request):
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to add accounts.")
        return redirect('finance:account_list')

    if request.method == 'POST':
        form = FinancialAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.created_by = request.user
            account.save()
            messages.success(request, f'Account "{account.name}" created successfully.')
            return redirect('finance:account_detail', pk=account.pk)
    else:
        form = FinancialAccountForm()

    return render(request, 'finance/account_form.html', {'form': form, 'account': None})


@finance_access_required
def account_edit(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to edit accounts.")
        return redirect('finance:account_detail', pk=pk)

    if request.method == 'POST':
        form = FinancialAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f'Account "{account.name}" updated successfully.')
            return redirect('finance:account_detail', pk=account.pk)
    else:
        form = FinancialAccountForm(instance=account)

    return render(request, 'finance/account_form.html', {'form': form, 'account': account})


@finance_access_required
def account_detail(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    recent_transactions = account.ledger_transactions.select_related(
        'related_client', 'related_vehicle', 'created_by', 'approved_by'
    )[:10]

    context = {
        'account': account,
        'recent_transactions': recent_transactions,
        'can_modify': _can_modify_finance(request.user),
        'can_record': _can_record_transactions(request.user),
    }
    return render(request, 'finance/account_detail.html', context)


@finance_access_required
def account_toggle_status(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to change account status.")
        return redirect('finance:account_detail', pk=pk)

    if request.method == 'POST':
        account.status = 'inactive' if account.status == 'active' else 'active'
        account.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Account "{account.name}" is now {account.get_status_display()}.')

    return redirect('finance:account_detail', pk=pk)


# ==================== LEDGER ====================

@finance_access_required
def account_ledger(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    transactions = account.ledger_transactions.select_related(
        'related_client', 'related_vehicle', 'created_by', 'approved_by'
    )

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    transaction_type = request.GET.get('transaction_type', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()

    if date_from:
        transactions = transactions.filter(transaction_date__gte=date_from)
    if date_to:
        transactions = transactions.filter(transaction_date__lte=date_to)
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if status:
        transactions = transactions.filter(status=status)
    if search:
        transactions = transactions.filter(
            Q(reference_number__icontains=search) | Q(description__icontains=search)
            | Q(related_party_label__icontains=search)
            | Q(related_client__first_name__icontains=search)
            | Q(related_client__last_name__icontains=search)
            | Q(related_vehicle__registration_number__icontains=search)
        )

    paginator = Paginator(transactions, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'account': account,
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'transaction_types': account.ledger_transactions.model.TRANSACTION_TYPE_CHOICES,
        'statuses': account.ledger_transactions.model.STATUS_CHOICES,
        'filters': {
            'date_from': date_from, 'date_to': date_to,
            'transaction_type': transaction_type, 'status': status, 'search': search,
        },
        'can_record': _can_record_transactions(request.user),
        'can_approve': _can_approve_transactions(request.user),
    }
    return render(request, 'finance/account_ledger.html', context)


# ==================== TRANSACTION ENTRY & APPROVAL ====================

@finance_access_required
def transaction_add(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    if not _can_record_transactions(request.user):
        messages.error(request, "You don't have permission to record transactions.")
        return redirect('finance:account_detail', pk=pk)
    if not account.allow_manual_transactions:
        messages.error(request, f'"{account.name}" does not allow manual transactions.')
        return redirect('finance:account_detail', pk=pk)

    if request.method == 'POST':
        form = LedgerTransactionForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            ledger_transaction = services.create_transaction(
                account,
                direction=data['direction'],
                transaction_type=data['transaction_type'],
                amount=data['amount'],
                created_by=request.user,
                transaction_date=data['transaction_date'],
                currency=data['currency'],
                source_module='manual',
                related_client=data.get('related_client'),
                related_vehicle=data.get('related_vehicle'),
                related_party_label=data.get('related_party_label', ''),
                payment_method=data.get('payment_method', ''),
                description=data.get('description', ''),
                supporting_document=data.get('supporting_document'),
            )
            if ledger_transaction.status == 'approved':
                messages.success(request, f'Transaction {ledger_transaction.reference_number} recorded and approved.')
            else:
                messages.success(request, f'Transaction {ledger_transaction.reference_number} recorded, pending approval.')
            return redirect('finance:transaction_detail', pk=ledger_transaction.pk)
    else:
        form = LedgerTransactionForm(initial={'currency': account.currency})

    return render(request, 'finance/transaction_form.html', {'form': form, 'account': account})


@finance_access_required
def transaction_detail(request, pk):
    ledger_transaction = get_object_or_404(
        LedgerTransaction.objects.select_related(
            'account', 'related_client', 'related_vehicle', 'created_by', 'approved_by', 'original_transaction'
        ),
        pk=pk,
    )
    transfer = InternalTransfer.objects.filter(
        Q(debit_transaction=ledger_transaction) | Q(credit_transaction=ledger_transaction)
    ).first()

    is_own = ledger_transaction.created_by_id == request.user.id
    can_approve = _can_approve_transactions(request.user) and not transfer
    can_edit = (
        ledger_transaction.status in ('draft', 'pending_approval', 'edit_requested')
        and not transfer
        and (is_own or can_approve)
        and _can_record_transactions(request.user)
    )

    context = {
        'transaction': ledger_transaction,
        'account': ledger_transaction.account,
        'transfer': transfer,
        'approvals': ledger_transaction.approvals.select_related('actioned_by'),
        'audit_trail': ledger_transaction.audit_trail.select_related('changed_by'),
        'related_entries': ledger_transaction.related_entries.select_related('created_by'),
        'can_approve': can_approve and ledger_transaction.status == 'pending_approval' and not is_own,
        'blocked_self_approval': can_approve and ledger_transaction.status == 'pending_approval' and is_own and not request.user.is_superuser,
        'can_request_edit': can_approve and ledger_transaction.status == 'pending_approval',
        'can_edit': can_edit,
        'can_reverse': (
            _can_reverse_transactions(request.user)
            and ledger_transaction.status == 'approved'
            and not ledger_transaction.is_reversal
        ),
    }
    return render(request, 'finance/transaction_detail.html', context)


@finance_access_required
def transaction_approve(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    if not _can_approve_transactions(request.user):
        messages.error(request, "You don't have permission to approve transactions.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        try:
            services.approve_transaction(
                ledger_transaction, request.user, comments,
                ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            messages.success(request, f'Transaction {ledger_transaction.reference_number} approved.')
        except PermissionError as exc:
            messages.error(request, str(exc))
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:transaction_detail', pk=pk)


@finance_access_required
def transaction_reject(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    if not _can_approve_transactions(request.user):
        messages.error(request, "You don't have permission to reject transactions.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        try:
            services.reject_transaction(
                ledger_transaction, request.user, comments,
                ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            messages.success(request, f'Transaction {ledger_transaction.reference_number} rejected.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:transaction_detail', pk=pk)


@finance_access_required
def transaction_request_edit(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    if not _can_approve_transactions(request.user):
        messages.error(request, "You don't have permission to request edits.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        try:
            services.request_transaction_edit(
                ledger_transaction, request.user, comments,
                ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            messages.success(request, f'Edit requested for {ledger_transaction.reference_number}.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:transaction_detail', pk=pk)


@finance_access_required
def transaction_edit(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    is_own = ledger_transaction.created_by_id == request.user.id
    can_approve = _can_approve_transactions(request.user)

    if ledger_transaction.status not in ('draft', 'pending_approval', 'edit_requested'):
        messages.error(request, 'Only draft, pending, or edit-requested transactions can be edited.')
        return redirect('finance:transaction_detail', pk=pk)
    if not (_can_record_transactions(request.user) and (is_own or can_approve)):
        messages.error(request, "You don't have permission to edit this transaction.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        form = LedgerTransactionEditForm(request.POST, request.FILES, instance=ledger_transaction)
        if form.is_valid():
            reason = form.cleaned_data.pop('edit_reason')
            field_updates = {
                field: form.cleaned_data[field] for field in services.EDITABLE_TRANSACTION_FIELDS
            }
            try:
                services.edit_transaction(
                    ledger_transaction, request.user, reason,
                    ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    **field_updates,
                )
                messages.success(request, f'Transaction {ledger_transaction.reference_number} updated.')
                return redirect('finance:transaction_detail', pk=pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = LedgerTransactionEditForm(instance=ledger_transaction)

    return render(request, 'finance/transaction_edit.html', {'form': form, 'transaction': ledger_transaction})


@finance_access_required
def transaction_reverse(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    if not _can_reverse_transactions(request.user):
        messages.error(request, "You don't have permission to reverse transactions.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        form = TransactionReversalForm(request.POST)
        if form.is_valid():
            try:
                reversal = services.reverse_transaction(
                    ledger_transaction, request.user, form.cleaned_data['reason'],
                    ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
                messages.success(request, f'{ledger_transaction.reference_number} reversed via {reversal.reference_number}.')
                return redirect('finance:transaction_detail', pk=pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = TransactionReversalForm()

    return render(request, 'finance/transaction_reverse.html', {'form': form, 'transaction': ledger_transaction})


@finance_access_required
def transaction_correct(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, pk=pk)
    if not _can_reverse_transactions(request.user):
        messages.error(request, "You don't have permission to correct transactions.")
        return redirect('finance:transaction_detail', pk=pk)

    if request.method == 'POST':
        form = TransactionCorrectionForm(request.POST)
        if form.is_valid():
            try:
                reversal, corrected = services.correct_transaction(
                    ledger_transaction, request.user,
                    form.cleaned_data['correct_amount'], form.cleaned_data['reason'],
                    ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
                messages.success(
                    request,
                    f'{ledger_transaction.reference_number} corrected: reversed via {reversal.reference_number}, '
                    f'new entry {corrected.reference_number}.'
                )
                return redirect('finance:transaction_detail', pk=corrected.pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = TransactionCorrectionForm(initial={'correct_amount': ledger_transaction.amount})

    return render(request, 'finance/transaction_correct.html', {'form': form, 'transaction': ledger_transaction})


@finance_access_required
def pending_approvals(request):
    transactions = LedgerTransaction.objects.filter(status='pending_approval').select_related(
        'account', 'related_client', 'related_vehicle', 'created_by'
    )

    paginator = Paginator(transactions, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'can_approve': _can_approve_transactions(request.user),
    }
    return render(request, 'finance/pending_approvals.html', context)


# ==================== INTERNAL TRANSFERS ====================

@finance_access_required
def transfer_add(request):
    if not _can_record_transactions(request.user):
        messages.error(request, "You don't have permission to record transfers.")
        return redirect('finance:account_list')

    if request.method == 'POST':
        form = InternalTransferForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                transfer = services.create_internal_transfer(
                    from_account=data['from_account'],
                    to_account=data['to_account'],
                    amount=data['amount'],
                    created_by=request.user,
                    transfer_date=data['transfer_date'],
                    notes=data.get('notes', ''),
                )
                messages.success(request, f'Transfer {transfer.transfer_reference} recorded.')
                return redirect('finance:transfer_detail', pk=transfer.pk)
            except ValueError as exc:
                form.add_error(None, str(exc))
    else:
        initial = {}
        from_pk = request.GET.get('from_account')
        if from_pk:
            initial['from_account'] = from_pk
        form = InternalTransferForm(initial=initial)

    return render(request, 'finance/transfer_form.html', {'form': form})


@finance_access_required
def transfer_detail(request, pk):
    transfer = get_object_or_404(
        InternalTransfer.objects.select_related(
            'from_account', 'to_account', 'debit_transaction', 'credit_transaction', 'created_by', 'approved_by'
        ),
        pk=pk,
    )
    context = {
        'transfer': transfer,
        'can_approve': _can_approve_transactions(request.user),
    }
    return render(request, 'finance/transfer_detail.html', context)


@finance_access_required
def transfer_approve(request, pk):
    transfer = get_object_or_404(InternalTransfer, pk=pk)
    if not _can_approve_transactions(request.user):
        messages.error(request, "You don't have permission to approve transfers.")
        return redirect('finance:transfer_detail', pk=pk)

    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        try:
            services.approve_internal_transfer(transfer, request.user, comments)
            messages.success(request, f'Transfer {transfer.transfer_reference} approved.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:transfer_detail', pk=pk)


@finance_access_required
def transfer_reject(request, pk):
    transfer = get_object_or_404(InternalTransfer, pk=pk)
    if not _can_approve_transactions(request.user):
        messages.error(request, "You don't have permission to reject transfers.")
        return redirect('finance:transfer_detail', pk=pk)

    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        try:
            services.reject_internal_transfer(transfer, request.user, comments)
            messages.success(request, f'Transfer {transfer.transfer_reference} rejected.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:transfer_detail', pk=pk)


# ==================== RECONCILIATION ====================

@finance_access_required
def account_reconciliation_list(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    reconciliations = account.reconciliations.select_related('reconciled_by').order_by('-reconciliation_date')
    context = {
        'account': account,
        'reconciliations': reconciliations,
        'can_modify': _can_modify_finance(request.user),
    }
    return render(request, 'finance/reconciliation_list.html', context)


@finance_access_required
def account_reconciliation_add(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to reconcile accounts.")
        return redirect('finance:account_reconciliation_list', pk=pk)

    if request.method == 'POST':
        form = AccountReconciliationForm(request.POST)
        if form.is_valid():
            reconciliation = form.save(commit=False)
            reconciliation.account = account
            reconciliation.book_balance = account.current_balance
            reconciliation.save()
            messages.success(
                request,
                f'Reconciliation started. Difference: {account.currency} {reconciliation.difference:,.2f}'
            )
            return redirect('finance:account_reconciliation_list', pk=pk)
    else:
        from django.utils import timezone
        form = AccountReconciliationForm(initial={'reconciliation_date': timezone.now().date()})

    return render(request, 'finance/reconciliation_form.html', {
        'form': form, 'account': account, 'book_balance': account.current_balance,
    })


@finance_access_required
def reconciliation_complete(request, pk):
    reconciliation = get_object_or_404(AccountReconciliation, pk=pk)
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to complete reconciliations.")
        return redirect('finance:account_reconciliation_list', pk=reconciliation.account_id)

    if request.method == 'POST':
        try:
            services.complete_reconciliation(reconciliation, request.user)
            messages.success(request, 'Reconciliation marked as completed.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('finance:account_reconciliation_list', pk=reconciliation.account_id)


# ==================== SUSPENSE ====================

@finance_access_required
def suspense_list(request):
    suspense_items = SuspenseTransaction.objects.filter(is_allocated=False).select_related(
        'transaction', 'transaction__account'
    ).order_by('-created_at')

    context = {
        'suspense_items': suspense_items,
        'can_modify': _can_modify_finance(request.user),
    }
    return render(request, 'finance/suspense_list.html', context)


@finance_access_required
def suspense_allocate(request, pk):
    suspense_txn = get_object_or_404(
        SuspenseTransaction.objects.select_related('transaction', 'transaction__account'), pk=pk
    )
    if not _can_modify_finance(request.user):
        messages.error(request, "You don't have permission to allocate suspense payments.")
        return redirect('finance:suspense_list')
    if suspense_txn.is_allocated:
        messages.error(request, 'This payment has already been allocated.')
        return redirect('finance:suspense_list')

    if request.method == 'POST':
        form = SuspenseAllocationForm(request.POST)
        if form.is_valid():
            try:
                services.allocate_suspense_transaction(
                    suspense_txn, request.user,
                    client=form.cleaned_data.get('client'),
                    client_vehicle=form.cleaned_data.get('client_vehicle'),
                    notes=form.cleaned_data.get('notes', ''),
                    ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
                messages.success(request, f'{suspense_txn.transaction.reference_number} allocated.')
                return redirect('finance:suspense_list')
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = SuspenseAllocationForm()

    return render(request, 'finance/suspense_allocate.html', {'form': form, 'suspense_txn': suspense_txn})


# ==================== REPORTS ====================

def _report_filters_from_request(request):
    return {
        'report_type': request.GET.get('report_type', 'all'),
        'account_id': request.GET.get('account', ''),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
        'transaction_type': request.GET.get('transaction_type', ''),
        'status': request.GET.get('status', ''),
        'search': request.GET.get('search', '').strip(),
    }


def _report_queryset(filters):
    account = FinancialAccount.objects.filter(pk=filters['account_id']).first() if filters['account_id'] else None
    return finance_reports.filter_transactions(
        filters['report_type'],
        account=account,
        date_from=filters['date_from'] or None,
        date_to=filters['date_to'] or None,
        transaction_type=filters['transaction_type'] or None,
        status=filters['status'] or None,
        search=filters['search'] or None,
    )


@finance_access_required
def reports(request):
    filters = _report_filters_from_request(request)
    qs = _report_queryset(filters)
    summary = finance_reports.summarize(qs)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'report_types': finance_reports.REPORT_TYPES,
        'accounts': FinancialAccount.objects.all().order_by('name'),
        'transaction_types': LedgerTransaction.TRANSACTION_TYPE_CHOICES,
        'statuses': LedgerTransaction.STATUS_CHOICES,
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'summary': summary,
        'filters': filters,
        'can_export': _can_export_finance(request.user),
    }
    return render(request, 'finance/reports.html', context)


@finance_access_required
def reports_export_csv(request):
    if not _can_export_finance(request.user):
        messages.error(request, "You don't have permission to export reports.")
        return redirect('finance:reports')

    filters = _report_filters_from_request(request)
    qs = _report_queryset(filters)

    report_label = dict(finance_reports.REPORT_TYPES).get(filters['report_type'], 'Transactions')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="finance_{filters["report_type"]}_{timezone.now().strftime("%Y%m%d")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Reference', 'Account', 'Source Module', 'Type', 'Direction', 'Amount', 'Currency',
        'Status', 'Client', 'Vehicle', 'Supplier/Vendor', 'Payment Method', 'Description',
        'Created By', 'Approved By',
    ])
    for txn in qs:
        writer.writerow([
            txn.transaction_date, txn.reference_number, txn.account.name, txn.get_source_module_display(),
            txn.get_transaction_type_display(), txn.get_direction_display(), txn.amount, txn.currency,
            txn.get_status_display(),
            str(txn.related_client) if txn.related_client else '',
            str(txn.related_vehicle) if txn.related_vehicle else '',
            txn.related_party_label,
            txn.get_payment_method_display() if txn.payment_method else '',
            txn.description,
            txn.created_by.get_full_name() if txn.created_by else '',
            txn.approved_by.get_full_name() if txn.approved_by else '',
        ])

    log_audit(request.user, 'export', 'LedgerTransaction', f'Exported {report_label} to CSV')
    return response


@finance_access_required
def financial_summary(request):
    period = request.GET.get('period', 'monthly')
    account_id = request.GET.get('account', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    account = FinancialAccount.objects.filter(pk=account_id).first() if account_id else None
    rows = finance_reports.period_summary(
        period, account=account, date_from=date_from or None, date_to=date_to or None,
    )

    context = {
        'periods': finance_reports.PERIOD_CHOICES,
        'accounts': FinancialAccount.objects.all().order_by('name'),
        'rows': rows,
        'filters': {'period': period, 'account_id': account_id, 'date_from': date_from, 'date_to': date_to},
        'can_export': _can_export_finance(request.user),
    }
    return render(request, 'finance/financial_summary.html', context)
