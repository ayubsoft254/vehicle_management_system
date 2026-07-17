"""
Reservation lifecycle services.

Handles proforma expiry, reservation expiry flagging and the pre-expiry
notifications sent to the responsible salesperson and managers. Called by
the `check_reservations` management command (cron) and opportunistically
whenever the proforma dashboard is opened, so state stays fresh even
without a scheduler.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from utils.constants import UserRole

from .models import ProformaInvoice, ReservationSetting, VehicleReservation

User = get_user_model()


def _notify(users, title, message, action_url, priority='high'):
    """Create in-app notifications, skipping duplicates for the same day/title."""
    from apps.notifications.models import Notification

    today = timezone.now().date()
    for user in users:
        if user is None:
            continue
        already = Notification.objects.filter(
            user=user, title=title, created_at__date=today
        ).exists()
        if already:
            continue
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type='vehicle',
            priority=priority,
            action_text='View Reservation',
            action_url=action_url,
        )


def _managers():
    return list(User.objects.filter(
        role__in=(UserRole.MANAGER, UserRole.ADMIN), is_active=True
    ))


def process_reservations():
    """
    * Expire proformas past their expiry date that never received a deposit.
    * Send pre-expiry warnings for reservations nearing their expiry date.
    * Flag reservations past expiry for manager review (deposit is NOT
      refunded and the vehicle is NOT auto-released — a manager must
      extend, cancel or release explicitly).
    """
    today = timezone.now().date()
    settings_obj = ReservationSetting.get_solo()

    # 1. Proformas past expiry with no confirmed deposit -> Expired
    stale = ProformaInvoice.objects.filter(
        status__in=('issued', 'awaiting_commitment'),
        expiry_date__lt=today,
    )
    for proforma in stale:
        if proforma.total_deposits_confirmed > 0:
            continue
        proforma.status = 'expired'
        proforma.save(update_fields=['status', 'updated_at'])

    # 2. Pre-expiry warnings
    warn_limit = today + timedelta(days=settings_obj.notify_days_before)
    expiring = VehicleReservation.objects.filter(
        status='active',
        expiry_notified=False,
        expiry_date__lte=warn_limit,
        expiry_date__gte=today,
    ).select_related('proforma__prepared_by', 'client', 'vehicle')
    for reservation in expiring:
        url = reverse('clients:proforma_detail', args=[reservation.proforma_id])
        recipients = [reservation.proforma.prepared_by, reservation.confirmed_by] + _managers()
        _notify(
            recipients,
            f'Reservation expiring: {reservation.vehicle.full_name}',
            (
                f'The reservation of {reservation.vehicle.full_name} for '
                f'{reservation.client.get_full_name()} (proforma '
                f'{reservation.proforma.number}) expires on '
                f'{reservation.expiry_date:%d %b %Y}. Deposit held: KES '
                f'{reservation.deposit_amount:,.2f}.'
            ),
            url,
        )
        reservation.expiry_notified = True
        reservation.save(update_fields=['expiry_notified', 'updated_at'])

    # 3. Reservations past expiry -> flag for review (no auto-refund/release)
    overdue = VehicleReservation.objects.filter(
        status='active',
        expiry_date__lt=today,
    ).select_related('proforma__prepared_by', 'client', 'vehicle')
    for reservation in overdue:
        with transaction.atomic():
            reservation.status = 'expired'
            reservation.save(update_fields=['status', 'updated_at'])
            url = reverse('clients:proforma_detail', args=[reservation.proforma_id])
            recipients = [reservation.proforma.prepared_by, reservation.confirmed_by] + _managers()
            _notify(
                recipients,
                f'Reservation expired — review needed: {reservation.vehicle.full_name}',
                (
                    f'The reservation of {reservation.vehicle.full_name} for '
                    f'{reservation.client.get_full_name()} (proforma '
                    f'{reservation.proforma.number}) expired on '
                    f'{reservation.expiry_date:%d %b %Y}. A manager must extend '
                    f'the reservation, cancel it, or release the vehicle. The '
                    f'deposit has NOT been refunded automatically.'
                ),
                url,
                priority='urgent',
            )
