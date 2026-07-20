"""
Proforma Invoice, Deposit Confirmation, Vehicle Reservation and
Proforma-to-Sale conversion views.

Business rules enforced here:
* A proforma invoice (or selecting bank financing) NEVER reserves a vehicle.
* A vehicle becomes Reserved only after the required deposit is confirmed.
* An expired reservation is flagged for manager review — never auto-refunded
  and never auto-released.
* Converting a proforma to a sale re-uses the held deposit; it is never
  duplicated in the client ledger or the account ledgers.
* Financial records are corrected by reversal, never deleted.
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.audit.utils import log_audit
from apps.payments.models import Account, AccountTransaction, Payment
from apps.vehicles.models import Vehicle
from utils.constants import AccessLevel, UserRole, VehicleStatus
from utils.decorators import module_permission_required, role_required

from .models import (
    Client, ClientVehicle, ProformaDeposit, ProformaInvoice,
    ReservationSetting, VehicleReservation,
)
from .reservation_services import process_reservations, _managers, _notify

ZERO = Decimal('0.00')

DEFAULT_TERMS_CONDITIONS = (
    '1. This proforma invoice is valid until the expiry date shown above.\n'
    '2. A proforma invoice does not reserve the vehicle. The vehicle remains '
    'on open sale until the required deposit is received and confirmed.\n'
    '3. Prices are quoted in Kenya Shillings and may be revised if the '
    'proforma expires before commitment.\n'
    '4. Deposits are only refundable in line with company policy.\n'
    '5. Ownership transfers only after full payment or financier '
    'disbursement is received.'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _audit(request, action, description, **kwargs):
    log_audit(
        request.user, action, 'ProformaInvoice', description,
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        request_path=request.path,
        request_method=request.method,
        **kwargs,
    )


def _can_confirm_deposit(user):
    """Cashiers/finance officers (accountant), managers and admins."""
    return user.is_superuser or user.role in (
        UserRole.ACCOUNTANT, UserRole.MANAGER, UserRole.ADMIN
    )


def _is_manager(user):
    return user.is_superuser or user.role in (UserRole.MANAGER, UserRole.ADMIN)


def _parse_money(value):
    try:
        amount = Decimal(str(value).replace(',', '').strip() or '0')
    except (InvalidOperation, AttributeError):
        return ZERO
    return amount.quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------

class ProformaInvoiceForm(forms.ModelForm):

    class Meta:
        model = ProformaInvoice
        fields = [
            'client', 'vehicle', 'issue_date', 'expiry_date', 'payment_mode',
            'financing_bank', 'selling_price', 'deposit_required',
            'financing_amount', 'total_price', 'company_account',
            'terms_conditions', 'notes',
        ]
        labels = {
            'deposit_required': 'Deposit Paid',
        }
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'terms_conditions': forms.Textarea(attrs={'rows': 5}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.filter(
            is_active=True).order_by('first_name', 'last_name')

        vehicle_qs = Vehicle.objects.filter(
            is_active=True, status=VehicleStatus.AVAILABLE
        ).order_by('-date_added')
        if self.instance.pk and self.instance.vehicle_id:
            vehicle_qs = Vehicle.objects.filter(
                Q(pk=self.instance.vehicle_id) |
                Q(is_active=True, status=VehicleStatus.AVAILABLE)
            ).order_by('-date_added')
        self.fields['vehicle'].queryset = vehicle_qs

        base_classes = (
            'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm '
            'focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        )
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {base_classes}'.strip()

    def clean(self):
        cleaned = super().clean()
        issue = cleaned.get('issue_date')
        expiry = cleaned.get('expiry_date')
        if issue and expiry and expiry < issue:
            self.add_error('expiry_date', 'Expiry date cannot be before the issue date.')
        if cleaned.get('payment_mode') == 'bank_financing' and not cleaned.get('financing_bank'):
            self.add_error('financing_bank', 'Select the financing bank/institution.')
        return cleaned


# ---------------------------------------------------------------------------
# List / dashboard
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_ONLY)
def proforma_list(request):
    """Proforma & reservation workbench: KPI cards + filterable list."""
    process_reservations()  # keep expiry state fresh even without cron

    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()

    proformas = ProformaInvoice.objects.select_related(
        'client', 'vehicle', 'prepared_by'
    ).prefetch_related('reservations')

    if status_filter:
        proformas = proformas.filter(status=status_filter)
    if search:
        proformas = proformas.filter(
            Q(number__icontains=search)
            | Q(client__first_name__icontains=search)
            | Q(client__last_name__icontains=search)
            | Q(vehicle__registration_number__icontains=search)
            | Q(vehicle__vin__icontains=search)
            | Q(vehicle__make__icontains=search)
            | Q(vehicle__model__icontains=search)
        )

    today = timezone.now().date()
    month_start = today.replace(day=1)
    all_proformas = ProformaInvoice.objects.all()

    expiring_soon = VehicleReservation.objects.filter(
        status='active', expiry_date__lte=today + timedelta(days=3)
    ).count()

    deposits_this_month = ProformaDeposit.objects.filter(
        is_reversed=False, payment_date__gte=month_start
    ).aggregate(t=Sum('amount'))['t'] or ZERO

    kpis = {
        'active': all_proformas.filter(status__in=ProformaInvoice.ACTIVE_STATUSES).count(),
        'awaiting_deposit': all_proformas.filter(
            status__in=('issued', 'awaiting_commitment')).count(),
        'reserved': VehicleReservation.objects.filter(status='active').count(),
        'expired_review': VehicleReservation.objects.filter(status='expired').count(),
        'expiring_soon': expiring_soon,
        'bank_financed': all_proformas.filter(
            payment_mode='bank_financing',
            status__in=ProformaInvoice.ACTIVE_STATUSES).count(),
        'deposits_this_month': deposits_this_month,
        'converted': all_proformas.filter(status='converted').count(),
        'expired_cancelled': all_proformas.filter(status__in=('expired', 'cancelled')).count(),
    }

    review_reservations = VehicleReservation.objects.filter(
        status='expired'
    ).select_related('client', 'vehicle', 'proforma')

    context = {
        'proformas': proformas[:200],
        'kpis': kpis,
        'status_filter': status_filter,
        'search': search,
        'status_choices': ProformaInvoice.STATUS_CHOICES,
        'review_reservations': review_reservations,
        'can_confirm_deposit': _can_confirm_deposit(request.user),
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'clients/proforma_list.html', context)


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_WRITE)
def proforma_create(request):
    initial = {
        'terms_conditions': DEFAULT_TERMS_CONDITIONS,
        'issue_date': timezone.now().date(),
        'expiry_date': timezone.now().date() + timedelta(days=14),
    }

    vehicle_id = request.GET.get('vehicle')
    if vehicle_id:
        vehicle = Vehicle.objects.filter(pk=vehicle_id).first()
        if vehicle:
            initial.update({
                'vehicle': vehicle,
                # website_price, not website_display_price — a proforma should
                # start at the publicly quoted price, or 0, never silently
                # fall back to the internal vehicle cost.
                'selling_price': vehicle.website_price or Decimal('0.00'),
                'total_price': vehicle.website_price or Decimal('0.00'),
                'deposit_required': vehicle.deposit_required,
            })
    client_id = request.GET.get('client')
    if client_id:
        client = Client.objects.filter(pk=client_id).first()
        if client:
            initial['client'] = client

    if request.method == 'POST':
        form = ProformaInvoiceForm(request.POST)
        if form.is_valid():
            proforma = form.save(commit=False)
            proforma.prepared_by = request.user
            proforma.status = 'draft'
            proforma.save()
            _audit(request, 'create',
                   f'Created proforma {proforma.number} for '
                   f'{proforma.client.get_full_name()} — {proforma.vehicle.full_name}',
                   object_id=str(proforma.pk))
            messages.success(request, f'Proforma {proforma.number} created as a draft.')
            return redirect('clients:proforma_detail', pk=proforma.pk)
    else:
        form = ProformaInvoiceForm(initial=initial)

    return render(request, 'clients/proforma_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
@module_permission_required('clients', AccessLevel.READ_WRITE)
def proforma_update(request, pk):
    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    if proforma.status not in ('draft', 'issued', 'awaiting_commitment'):
        messages.error(request, 'Only proformas without a confirmed deposit can be edited.')
        return redirect('clients:proforma_detail', pk=pk)

    if request.method == 'POST':
        form = ProformaInvoiceForm(request.POST, instance=proforma)
        if form.is_valid():
            changes = {
                name: {'old': str(form.initial.get(name, '')), 'new': str(form.cleaned_data.get(name, ''))}
                for name in form.changed_data
            }
            form.save()
            _audit(request, 'update', f'Updated proforma {proforma.number}',
                   object_id=str(proforma.pk), changes=changes)
            messages.success(request, f'Proforma {proforma.number} updated.')
            return redirect('clients:proforma_detail', pk=pk)
    else:
        form = ProformaInvoiceForm(instance=proforma)

    return render(request, 'clients/proforma_form.html', {
        'form': form,
        'is_edit': True,
        'proforma': proforma,
    })


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_ONLY)
def proforma_detail(request, pk):
    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related(
            'client', 'vehicle', 'prepared_by', 'converted_client_vehicle'
        ),
        pk=pk,
    )
    deposits = proforma.deposits.select_related(
        'confirmed_by', 'account', 'converted_payment').order_by('-payment_date')
    reservations = proforma.reservations.select_related(
        'confirmed_by', 'released_by').order_by('-reserved_at')

    settings_obj = ReservationSetting.get_solo()

    context = {
        'proforma': proforma,
        'deposits': deposits,
        'reservations': reservations,
        'reservation': proforma.active_reservation,
        'accounts': Account.objects.filter(is_active=True).order_by('category', 'name'),
        'payment_methods': ProformaDeposit.PAYMENT_METHOD_CHOICES,
        'reservation_setting': settings_obj,
        'can_confirm_deposit': _can_confirm_deposit(request.user),
        'is_manager': _is_manager(request.user),
        'today': timezone.now().date(),
    }
    return render(request, 'clients/proforma_detail.html', context)


# ---------------------------------------------------------------------------
# Status actions
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_WRITE)
def proforma_issue(request, pk):
    """Issue a draft proforma to the client (no vehicle impact whatsoever)."""
    if request.method != 'POST':
        return redirect('clients:proforma_detail', pk=pk)
    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    if proforma.status != 'draft':
        messages.error(request, 'Only draft proformas can be issued.')
        return redirect('clients:proforma_detail', pk=pk)

    old_status = proforma.status
    proforma.status = (
        'awaiting_commitment' if proforma.payment_mode == 'bank_financing' else 'issued'
    )
    proforma.approval_status = 'approved'
    proforma.approved_by = request.user
    proforma.save(update_fields=['status', 'approval_status', 'approved_by', 'updated_at'])

    _audit(request, 'update',
           f'Issued proforma {proforma.number} ({old_status} → {proforma.status}). '
           f'Vehicle remains {proforma.vehicle.get_status_display()} — no reservation.',
           object_id=str(proforma.pk),
           changes={'status': {'old': old_status, 'new': proforma.status}})
    messages.success(
        request,
        f'Proforma {proforma.number} issued. The vehicle stays available for '
        f'sale until a deposit is confirmed.'
    )
    return redirect('clients:proforma_detail', pk=pk)


@login_required
@module_permission_required('clients', AccessLevel.READ_WRITE)
def proforma_cancel(request, pk):
    if request.method != 'POST':
        return redirect('clients:proforma_detail', pk=pk)
    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    reason = request.POST.get('reason', '').strip()

    if proforma.status in ('converted', 'cancelled'):
        messages.error(request, 'This proforma can no longer be cancelled.')
        return redirect('clients:proforma_detail', pk=pk)
    if not reason:
        messages.error(request, 'A reason is required to cancel a proforma.')
        return redirect('clients:proforma_detail', pk=pk)
    if proforma.status in ('deposit_paid', 'reserved') and not _is_manager(request.user):
        messages.error(request, 'Only a manager can cancel a proforma with a confirmed deposit.')
        return redirect('clients:proforma_detail', pk=pk)

    with transaction.atomic():
        old_status = proforma.status
        reservation = proforma.active_reservation
        if reservation:
            reservation.status = 'cancelled'
            reservation.released_by = request.user
            reservation.released_at = timezone.now()
            reservation.release_reason = f'Proforma cancelled: {reason}'
            reservation.save(update_fields=[
                'status', 'released_by', 'released_at', 'release_reason', 'updated_at'])
            vehicle = proforma.vehicle
            if vehicle.status == VehicleStatus.RESERVED:
                vehicle.change_status(
                    VehicleStatus.AVAILABLE, request.user,
                    notes=f'Reservation cancelled with proforma {proforma.number}: {reason}')

        proforma.status = 'cancelled'
        proforma.cancelled_by = request.user
        proforma.cancelled_at = timezone.now()
        proforma.cancel_reason = reason
        proforma.save(update_fields=[
            'status', 'cancelled_by', 'cancelled_at', 'cancel_reason', 'updated_at'])

    _audit(request, 'update',
           f'Cancelled proforma {proforma.number}. Reason: {reason}',
           object_id=str(proforma.pk),
           changes={'status': {'old': old_status, 'new': 'cancelled'},
                    'reason': reason})
    messages.success(request, f'Proforma {proforma.number} cancelled. '
                              f'Deposit history has been preserved.')
    return redirect('clients:proforma_detail', pk=pk)


# ---------------------------------------------------------------------------
# Deposit confirmation -> reservation
# ---------------------------------------------------------------------------

@login_required
def confirm_deposit(request, pk):
    """
    Confirm a commitment deposit (cashier/finance/manager/admin only).

    Posts the money into the selected account ledger (debit), shows as a
    credit on the client statement, links to the proforma, and — once the
    required deposit is fully covered — reserves the vehicle.
    """
    if request.method != 'POST':
        return redirect('clients:proforma_detail', pk=pk)
    if not _can_confirm_deposit(request.user):
        messages.error(request, 'Only cashiers, finance officers or managers can confirm deposits.')
        return redirect('clients:proforma_detail', pk=pk)

    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related('client', 'vehicle'), pk=pk)

    if proforma.status not in ('issued', 'awaiting_commitment', 'deposit_paid', 'reserved'):
        messages.error(request, 'Deposits can only be confirmed on an issued, active proforma.')
        return redirect('clients:proforma_detail', pk=pk)

    amount = _parse_money(request.POST.get('amount'))
    if amount <= 0:
        messages.error(request, 'Enter a valid deposit amount.')
        return redirect('clients:proforma_detail', pk=pk)

    payment_method = request.POST.get('payment_method', 'cash')
    reference = request.POST.get('transaction_reference', '').strip()
    notes = request.POST.get('notes', '').strip()

    payment_date = timezone.now().date()
    date_str = request.POST.get('payment_date', '').strip()
    if date_str:
        try:
            payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    account = None
    account_id = request.POST.get('account', '').strip()
    if account_id:
        account = Account.objects.filter(pk=account_id, is_active=True).first()

    vehicle = proforma.vehicle
    existing_reservation = proforma.active_reservation

    # The vehicle must still be sellable to THIS client. If another client
    # got there first, do not take the money — surface the conflict.
    if existing_reservation is None and vehicle.status != VehicleStatus.AVAILABLE:
        messages.error(
            request,
            f'{vehicle.full_name} is no longer available '
            f'({vehicle.get_status_display()}). The deposit was NOT recorded — '
            f'please resolve with the client before taking money.'
        )
        return redirect('clients:proforma_detail', pk=pk)

    with transaction.atomic():
        deposit = ProformaDeposit.objects.create(
            proforma=proforma,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            transaction_reference=reference,
            account=account,
            notes=notes,
            confirmed_by=request.user,
        )

        if account:
            account_txn = AccountTransaction.objects.create(
                account=account,
                transaction_type='money_in',
                direction='in',
                amount=amount,
                date=payment_date,
                payment_method=dict(ProformaDeposit.PAYMENT_METHOD_CHOICES).get(
                    payment_method, payment_method),
                reference=reference or proforma.number,
                narration=(
                    f'Proforma deposit {proforma.number} — '
                    f'{proforma.client.get_full_name()} — {vehicle.full_name}'
                ),
                related_client=proforma.client,
                related_vehicle=vehicle,
                created_by=request.user,
                approval_status='approved',
            )
            deposit.account_transaction = account_txn
            deposit.save(update_fields=['account_transaction'])

        old_status = proforma.status
        proforma.status = 'deposit_paid'
        proforma.save(update_fields=['status', 'updated_at'])

        reservation_created = False
        if existing_reservation is None and proforma.deposit_fully_paid:
            settings_obj = ReservationSetting.get_solo()
            period_raw = request.POST.get('reservation_period', '').strip()
            expiry_date = None
            period_days = settings_obj.default_period_days

            if period_raw == 'custom':
                custom = request.POST.get('custom_expiry_date', '').strip()
                try:
                    expiry_date = datetime.strptime(custom, '%Y-%m-%d').date()
                    period_days = max(1, (expiry_date - timezone.now().date()).days)
                except ValueError:
                    expiry_date = None
            elif period_raw.isdigit():
                period_days = int(period_raw)

            if expiry_date is None:
                expiry_date = timezone.now().date() + timedelta(days=period_days)

            reservation = VehicleReservation.objects.create(
                proforma=proforma,
                client=proforma.client,
                vehicle=vehicle,
                deposit=deposit,
                period_days=period_days,
                expiry_date=expiry_date,
                confirmed_by=request.user,
            )
            vehicle.change_status(
                VehicleStatus.RESERVED, request.user,
                notes=(
                    f'Reserved for {proforma.client.get_full_name()} — deposit '
                    f'KES {amount:,.2f} confirmed on proforma {proforma.number}. '
                    f'Expires {expiry_date:%d %b %Y}.'
                ),
            )
            proforma.status = 'reserved'
            proforma.save(update_fields=['status', 'updated_at'])
            reservation_created = True

    _audit(request, 'create',
           f'Confirmed deposit KES {amount:,.2f} on proforma {proforma.number} '
           f'({dict(ProformaDeposit.PAYMENT_METHOD_CHOICES).get(payment_method, payment_method)}'
           f'{", account: " + account.name if account else ""})',
           object_id=str(proforma.pk),
           changes={'status': {'old': old_status, 'new': proforma.status},
                    'deposit_amount': str(amount)})

    if reservation_created:
        _notify(
            [proforma.prepared_by] + _managers(),
            f'Vehicle reserved: {vehicle.full_name}',
            (
                f'{proforma.client.get_full_name()} paid a deposit of KES '
                f'{amount:,.2f} on proforma {proforma.number}. The vehicle is '
                f'now reserved until {proforma.active_reservation.expiry_date:%d %b %Y}.'
            ),
            reverse('clients:proforma_detail', args=[proforma.pk]),
        )
        messages.success(
            request,
            f'Deposit of KES {amount:,.2f} confirmed and {vehicle.full_name} '
            f'is now RESERVED for {proforma.client.get_full_name()}.'
        )
    else:
        outstanding = proforma.deposit_outstanding
        if outstanding > 0:
            messages.success(
                request,
                f'Deposit of KES {amount:,.2f} confirmed. KES {outstanding:,.2f} '
                f'more is required before the vehicle is reserved.'
            )
        else:
            messages.success(request, f'Deposit of KES {amount:,.2f} confirmed.')

    return redirect('clients:proforma_detail', pk=pk)


@login_required
def reverse_deposit(request, pk, deposit_pk):
    """Reverse a wrongly-captured deposit (manager/admin only, reason required)."""
    if request.method != 'POST':
        return redirect('clients:proforma_detail', pk=pk)
    if not _is_manager(request.user):
        messages.error(request, 'Only a manager can reverse a deposit.')
        return redirect('clients:proforma_detail', pk=pk)

    proforma = get_object_or_404(ProformaInvoice, pk=pk)
    deposit = get_object_or_404(ProformaDeposit, pk=deposit_pk, proforma=proforma)
    reason = request.POST.get('reason', '').strip()

    if deposit.converted_payment_id:
        messages.error(request, 'This deposit was converted into a sale payment — '
                                'reverse the payment through reconciliation instead.')
        return redirect('clients:proforma_detail', pk=pk)

    try:
        deposit.reverse(request.user, reason)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('clients:proforma_detail', pk=pk)

    _audit(request, 'update',
           f'Reversed deposit KES {deposit.amount:,.2f} on proforma '
           f'{proforma.number}. Reason: {reason}',
           object_id=str(proforma.pk),
           changes={'deposit': str(deposit.pk), 'reason': reason})
    messages.success(request, 'Deposit reversed. The entry remains visible for audit.')
    return redirect('clients:proforma_detail', pk=pk)


# ---------------------------------------------------------------------------
# Reservation management (manager only)
# ---------------------------------------------------------------------------

@login_required
def reservation_extend(request, pk):
    if request.method != 'POST':
        return redirect('clients:proforma_list')
    if not _is_manager(request.user):
        messages.error(request, 'Only a manager can extend a reservation.')
        return redirect('clients:proforma_list')

    reservation = get_object_or_404(
        VehicleReservation.objects.select_related('proforma', 'vehicle', 'client'), pk=pk)
    if reservation.status not in ('active', 'expired'):
        messages.error(request, 'Only active or expired reservations can be extended.')
        return redirect('clients:proforma_detail', pk=reservation.proforma_id)

    new_date_str = request.POST.get('new_expiry_date', '').strip()
    try:
        new_expiry = datetime.strptime(new_date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Enter a valid new expiry date.')
        return redirect('clients:proforma_detail', pk=reservation.proforma_id)
    if new_expiry <= timezone.now().date():
        messages.error(request, 'The new expiry date must be in the future.')
        return redirect('clients:proforma_detail', pk=reservation.proforma_id)

    old_expiry = reservation.expiry_date
    reservation.expiry_date = new_expiry
    reservation.status = 'active'
    reservation.extension_count += 1
    reservation.extended_by = request.user
    reservation.extended_at = timezone.now()
    reservation.expiry_notified = False
    reservation.save(update_fields=[
        'expiry_date', 'status', 'extension_count', 'extended_by',
        'extended_at', 'expiry_notified', 'updated_at'])

    _audit(request, 'update',
           f'Extended reservation on {reservation.vehicle.full_name} '
           f'({reservation.proforma.number}) from {old_expiry} to {new_expiry}',
           object_id=str(reservation.proforma_id),
           changes={'expiry_date': {'old': str(old_expiry), 'new': str(new_expiry)}})
    messages.success(request, f'Reservation extended to {new_expiry:%d %b %Y}.')
    return redirect('clients:proforma_detail', pk=reservation.proforma_id)


@login_required
def reservation_release(request, pk):
    """Release the vehicle back to Available stock (manager only)."""
    if request.method != 'POST':
        return redirect('clients:proforma_list')
    if not _is_manager(request.user):
        messages.error(request, 'Only a manager can release a reserved vehicle.')
        return redirect('clients:proforma_list')

    reservation = get_object_or_404(
        VehicleReservation.objects.select_related('proforma', 'vehicle', 'client'), pk=pk)
    reason = request.POST.get('reason', '').strip()
    if reservation.status not in ('active', 'expired'):
        messages.error(request, 'This reservation is no longer active.')
        return redirect('clients:proforma_detail', pk=reservation.proforma_id)
    if not reason:
        messages.error(request, 'A reason is required to release a reserved vehicle.')
        return redirect('clients:proforma_detail', pk=reservation.proforma_id)

    with transaction.atomic():
        old_status = reservation.status
        reservation.status = 'released'
        reservation.released_by = request.user
        reservation.released_at = timezone.now()
        reservation.release_reason = reason
        reservation.save(update_fields=[
            'status', 'released_by', 'released_at', 'release_reason', 'updated_at'])

        vehicle = reservation.vehicle
        if vehicle.status == VehicleStatus.RESERVED:
            vehicle.change_status(
                VehicleStatus.AVAILABLE, request.user,
                notes=f'Reservation released ({reservation.proforma.number}): {reason}')

        proforma = reservation.proforma
        if proforma.status in ('deposit_paid', 'reserved'):
            proforma.status = 'expired'
            proforma.save(update_fields=['status', 'updated_at'])

    _audit(request, 'update',
           f'Released reserved vehicle {reservation.vehicle.full_name} '
           f'({reservation.proforma.number}). Reason: {reason}. '
           f'Deposit of KES {reservation.deposit_amount:,.2f} retained pending decision.',
           object_id=str(reservation.proforma_id),
           changes={'reservation_status': {'old': old_status, 'new': 'released'},
                    'reason': reason})
    messages.success(
        request,
        f'{reservation.vehicle.full_name} returned to available stock. Client, '
        f'payment, proforma and reservation history have been preserved.'
    )
    return redirect('clients:proforma_detail', pk=reservation.proforma_id)


# ---------------------------------------------------------------------------
# Conversion to sale
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_WRITE)
def convert_proforma(request, pk):
    """
    Convert a committed proforma into an official sale (ClientVehicle).

    The held deposit becomes a normal Payment on the sale — exactly once.
    Where the deposit was posted to a legacy account (whose ledger is
    computed from Payment rows), the original AccountTransaction is
    reversed so the money never appears twice in that account's ledger.
    """
    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related('client', 'vehicle'), pk=pk)

    if proforma.status not in ('deposit_paid', 'reserved'):
        messages.error(
            request,
            'Only a proforma with a confirmed deposit can be converted to a sale.')
        return redirect('clients:proforma_detail', pk=pk)

    if ClientVehicle.objects.filter(client=proforma.client, vehicle=proforma.vehicle).exists():
        messages.error(request, 'A sale record already exists for this client and vehicle.')
        return redirect('clients:proforma_detail', pk=pk)

    if request.method != 'POST':
        return redirect('clients:proforma_detail', pk=pk)

    payment_type = request.POST.get('payment_type', 'installment')
    if payment_type not in ('full', 'installment', 'flexible'):
        payment_type = 'installment'
    final_price = _parse_money(request.POST.get('final_price')) or proforma.total_price

    with transaction.atomic():
        deposits = list(proforma.deposits.filter(
            is_reversed=False, converted_payment__isnull=True))
        deposit_total = sum((d.amount for d in deposits), ZERO)

        client_vehicle = ClientVehicle.objects.create(
            client=proforma.client,
            vehicle=proforma.vehicle,
            purchase_date=timezone.now().date(),
            purchase_price=final_price,
            client_purchase_price=final_price,
            final_selling_price=final_price,
            deposit_paid=deposit_total,
            total_paid=deposit_total,
            balance=final_price - deposit_total,
            payment_type=payment_type,
            created_by=request.user,
            notes=(
                f'Converted from proforma {proforma.number}. '
                f'Financing: {proforma.get_payment_mode_display()}'
                f'{" — " + proforma.financing_bank if proforma.financing_bank else ""}.'
            ),
        )

        # Move each held deposit into the official payment allocation —
        # never duplicated.
        for deposit in deposits:
            payment = Payment.objects.create(
                client_vehicle=client_vehicle,
                amount=deposit.amount,
                payment_date=deposit.payment_date,
                payment_method=deposit.payment_method,
                transaction_reference=deposit.transaction_reference or None,
                notes=f'Commitment deposit transferred from proforma {proforma.number}',
                recorded_by=deposit.confirmed_by or request.user,
            )
            deposit.converted_payment = payment
            deposit.save(update_fields=['converted_payment'])

            # Legacy accounts compute their ledger from Payment rows by
            # payment_method — reverse the original AccountTransaction so
            # the deposit is not double-counted there. Non-legacy accounts
            # only see AccountTransactions, so theirs is kept.
            txn = deposit.account_transaction
            if txn and not txn.is_reversed and deposit.account and \
                    deposit.account.payment_method_code == deposit.payment_method:
                txn.reverse(
                    request.user,
                    f'Superseded by payment {payment.receipt_number} on conversion '
                    f'of proforma {proforma.number} (prevents double counting).',
                )

        vehicle = proforma.vehicle
        vehicle.selling_price = final_price
        vehicle.save(update_fields=['selling_price', 'last_updated'])
        vehicle.change_status(
            VehicleStatus.SOLD, request.user,
            notes=f'Sold to {proforma.client.get_full_name()} — converted from '
                  f'proforma {proforma.number}')

        for reservation in proforma.reservations.filter(status__in=('active', 'expired')):
            reservation.status = 'converted'
            reservation.save(update_fields=['status', 'updated_at'])

        proforma.status = 'converted'
        proforma.converted_client_vehicle = client_vehicle
        proforma.converted_at = timezone.now()
        proforma.converted_by = request.user
        proforma.save(update_fields=[
            'status', 'converted_client_vehicle', 'converted_at',
            'converted_by', 'updated_at'])

        client = proforma.client
        if client.status != 'active':
            client.status = 'active'
            client.save(update_fields=['status'])

    _audit(request, 'create',
           f'Converted proforma {proforma.number} into sale CV-{client_vehicle.pk}. '
           f'Deposit of KES {deposit_total:,.2f} transferred (not duplicated). '
           f'Balance: KES {client_vehicle.balance:,.2f}.',
           object_id=str(proforma.pk),
           changes={'status': {'old': 'reserved', 'new': 'converted'},
                    'client_vehicle': str(client_vehicle.pk)})

    messages.success(
        request,
        f'Proforma {proforma.number} converted to a sale. Deposit of KES '
        f'{deposit_total:,.2f} was transferred to the vehicle payment '
        f'allocation. Set up the installment plan and sales agreement below.'
    )
    return redirect('clients:client_vehicle_detail', pk=client_vehicle.pk)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@login_required
@module_permission_required('clients', AccessLevel.READ_ONLY)
def proforma_pdf(request, pk):
    """Professional, printable proforma invoice PDF — compressed to fit a
    single page: dense multi-field-per-row tables instead of one field per
    row, tight padding, and a preselected Company Account block."""
    from utils.report_kit import build_pdf_response, fmt_money, BORDER_GREY, LIGHT_GREY
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related('client', 'vehicle', 'prepared_by'),
        pk=pk,
    )
    client = proforma.client
    vehicle = proforma.vehicle

    def body(elements, styles):
        compact = ParagraphStyle('ProformaCompact', parent=styles['Normal'], fontSize=8, leading=10)
        heading = styles['ReportSectionHeading']
        heading.spaceBefore = 6
        heading.spaceAfter = 3

        def field_grid(pairs, col_widths):
            """Lay out (label, value) pairs several-per-row as bold-label
            Paragraphs inside one dense table, instead of one field per row."""
            rows, row = [], []
            for label, value in pairs:
                row.append(Paragraph(f'<b>{label}:</b> {value}', compact))
                if len(row) == len(col_widths):
                    rows.append(row)
                    row = []
            if row:
                row += [''] * (len(col_widths) - len(row))
                rows.append(row)
            table = Table(rows, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
            ]))
            return table

        # One continuous 2-column grid for client + vehicle fields, matching
        # the Financial Summary table's column count.
        elements.append(Paragraph('CLIENT &amp; VEHICLE DETAILS', heading))
        elements.append(field_grid([
            ('Name', client.get_full_name()),
            (client.get_id_type_display(), client.id_number),
            ('Phone', client.phone_primary or '—'),
            ('Email', client.email or '—'),
            ('Reg No', vehicle.registration_number or '—'),
            ('Chassis No', vehicle.vin),
            ('Make / Model', f'{vehicle.make} {vehicle.model}'),
            ('Year', vehicle.year),
            ('Engine', vehicle.engine_size or '—'),
            ('Colour', vehicle.color or '—'),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('FINANCIAL SUMMARY', heading))
        financial_pairs = []
        if proforma.payment_mode == 'bank_financing':
            financial_pairs.append(('Bank / Institution', proforma.financing_bank or '—'))
        financial_pairs += [
            ('Selling Price', fmt_money(proforma.selling_price)),
            ('Deposit Paid', fmt_money(proforma.total_deposits_confirmed)),
            ('Balance', fmt_money(proforma.remaining_balance)),
        ]
        elements.append(field_grid(financial_pairs, col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        account = proforma.get_company_account_details()
        if account:
            elements.append(Paragraph('COMPANY ACCOUNT', heading))
            elements.append(field_grid([
                ('Bank', account['bank']),
                ('Branch', account['branch']),
                ('Account Name', account['account_name']),
                ('Account No', account['account_number']),
            ], col_widths=[3.25 * inch, 3.25 * inch]))
            elements.append(Spacer(1, 6))

        if proforma.terms_conditions:
            elements.append(Paragraph('TERMS &amp; CONDITIONS', heading))
            for line in proforma.terms_conditions.splitlines():
                if line.strip():
                    elements.append(Paragraph(line.strip(), compact))
            elements.append(Spacer(1, 6))

        prepared = proforma.prepared_by.get_full_name() if proforma.prepared_by else '—'
        elements.append(field_grid([
            ('Prepared By', prepared),
            ('Approval Status', proforma.get_approval_status_display()),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph('www.hozacars.com', styles['ReportCompanyMeta']))

    _audit(request, 'export', f'Downloaded proforma PDF {proforma.number}',
           object_id=str(proforma.pk))

    return build_pdf_response(
        f'{proforma.number}.pdf',
        'Proforma Invoice',
        subtitle=f'{proforma.number} — {client.get_full_name()}',
        build_body=body,
    )


@login_required
@module_permission_required('clients', AccessLevel.READ_ONLY)
def proforma_deposit_receipt(request, pk, deposit_pk):
    """Printable PDF receipt for a single confirmed commitment deposit."""
    from utils.report_kit import build_pdf_response, fmt_money, BORDER_GREY, LIGHT_GREY
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    proforma = get_object_or_404(
        ProformaInvoice.objects.select_related('client', 'vehicle'), pk=pk
    )
    deposit = get_object_or_404(
        ProformaDeposit.objects.select_related('confirmed_by', 'account', 'converted_payment'),
        pk=deposit_pk, proforma=proforma,
    )
    client = proforma.client
    vehicle = proforma.vehicle

    def body(elements, styles):
        compact = ParagraphStyle('ReceiptCompact', parent=styles['Normal'], fontSize=8, leading=10)
        heading = styles['ReportSectionHeading']
        heading.spaceBefore = 6
        heading.spaceAfter = 3

        def field_grid(pairs, col_widths):
            rows, row = [], []
            for label, value in pairs:
                row.append(Paragraph(f'<b>{label}:</b> {value}', compact))
                if len(row) == len(col_widths):
                    rows.append(row)
                    row = []
            if row:
                row += [''] * (len(col_widths) - len(row))
                rows.append(row)
            table = Table(rows, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
            ]))
            return table

        if deposit.is_reversed:
            status = 'REVERSED'
        elif deposit.converted_payment:
            status = 'Transferred to Sale'
        else:
            status = 'Held'

        elements.append(Paragraph('CLIENT &amp; VEHICLE DETAILS', heading))
        elements.append(field_grid([
            ('Name', client.get_full_name()),
            (client.get_id_type_display(), client.id_number),
            ('Phone', client.phone_primary or '—'),
            ('Proforma No', proforma.number),
            ('Reg No', vehicle.registration_number or '—'),
            ('Chassis No', vehicle.vin),
            ('Make / Model', f'{vehicle.make} {vehicle.model}'),
            ('Year', vehicle.year),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('DEPOSIT DETAILS', heading))
        elements.append(field_grid([
            ('Amount', fmt_money(deposit.amount)),
            ('Payment Date', deposit.payment_date.strftime('%d %B %Y')),
            ('Method', deposit.get_payment_method_display()),
            ('Account', deposit.account.name if deposit.account else '—'),
            ('Reference', deposit.transaction_reference or '—'),
            ('Confirmed By', deposit.confirmed_by.get_full_name() if deposit.confirmed_by else '—'),
            ('Status', status),
            ('Confirmed At', deposit.confirmed_at.strftime('%d %B %Y, %H:%M')),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        if deposit.is_reversed:
            elements.append(Paragraph(
                'This deposit was later reversed and no longer counts towards the '
                'reservation or client balance. This receipt is kept for audit purposes only.',
                compact,
            ))
            elements.append(Spacer(1, 6))

        elements.append(Paragraph(
            'This receipt confirms a commitment deposit held against the proforma '
            'invoice above. It is not a receipt for the full vehicle purchase price.',
            compact,
        ))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph('www.hozacars.com', styles['ReportCompanyMeta']))

    _audit(request, 'export', f'Downloaded deposit receipt for proforma {proforma.number}',
           object_id=str(deposit.pk))

    return build_pdf_response(
        f'deposit-receipt-{proforma.number}-{deposit.pk}.pdf',
        'Deposit Receipt',
        subtitle=f'{proforma.number} — {client.get_full_name()}',
        build_body=body,
    )


# ---------------------------------------------------------------------------
# Reservation settings (admin only)
# ---------------------------------------------------------------------------

@login_required
@role_required(UserRole.ADMIN)
def reservation_settings(request):
    settings_obj = ReservationSetting.get_solo()

    if request.method == 'POST':
        try:
            period = int(request.POST.get('default_period_days', settings_obj.default_period_days))
            notify_days = int(request.POST.get('notify_days_before', settings_obj.notify_days_before))
            if period < 1 or notify_days < 0:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Enter valid positive numbers.')
            return redirect('clients:reservation_settings')

        old = {'default_period_days': settings_obj.default_period_days,
               'notify_days_before': settings_obj.notify_days_before}
        settings_obj.default_period_days = period
        settings_obj.notify_days_before = notify_days
        settings_obj.updated_by = request.user
        settings_obj.save()

        _audit(request, 'update',
               f'Updated reservation settings: default period {period} days, '
               f'notify {notify_days} day(s) before expiry',
               changes={'old': old,
                        'new': {'default_period_days': period,
                                'notify_days_before': notify_days}})
        messages.success(request, 'Reservation settings updated.')
        return redirect('clients:proforma_list')

    return render(request, 'clients/reservation_settings.html', {
        'setting': settings_obj,
        'period_choices': ReservationSetting.PERIOD_CHOICES,
    })
