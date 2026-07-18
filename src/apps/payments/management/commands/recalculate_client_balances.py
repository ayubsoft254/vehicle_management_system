"""
Recalculate client vehicle balances from recorded payment ledger entries.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.clients.models import Client, ClientVehicle
from apps.payments.models import Payment


class Command(BaseCommand):
    help = (
        "Recalculate ClientVehicle total_paid/balance/is_paid_off from Payment records "
        "and update each client's current_debt/status."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()

        payment_totals = dict(
            Payment.objects.filter(payment_date__lte=today, is_reversed=False)
            .values('client_vehicle_id')
            .annotate(total=Sum('amount'))
            .values_list('client_vehicle_id', 'total')
        )

        updated_vehicles = 0
        updated_clients = 0
        processed_vehicles = 0

        self.stdout.write(self.style.NOTICE('Starting client balance recalculation...'))

        def recalc():
            nonlocal updated_vehicles, updated_clients, processed_vehicles

            vehicles = ClientVehicle.objects.select_related('client').all()
            for vehicle in vehicles.iterator():
                processed_vehicles += 1
                expected_total_paid = payment_totals.get(vehicle.id) or Decimal('0.00')
                expected_balance = vehicle.purchase_price - expected_total_paid
                expected_is_paid_off = expected_balance <= Decimal('0.00')
                expected_date_paid_off = vehicle.date_paid_off

                if expected_is_paid_off:
                    expected_balance = Decimal('0.00')
                    if expected_date_paid_off is None:
                        expected_date_paid_off = today
                else:
                    expected_date_paid_off = None

                changed = (
                    vehicle.total_paid != expected_total_paid
                    or vehicle.balance != expected_balance
                    or vehicle.is_paid_off != expected_is_paid_off
                    or vehicle.date_paid_off != expected_date_paid_off
                )

                if changed:
                    vehicle.total_paid = expected_total_paid
                    vehicle.balance = expected_balance
                    vehicle.is_paid_off = expected_is_paid_off
                    vehicle.date_paid_off = expected_date_paid_off
                    vehicle.save(update_fields=['total_paid', 'balance', 'is_paid_off', 'date_paid_off'])
                    updated_vehicles += 1

            clients = Client.objects.all()
            for client in clients.iterator():
                expected_debt = client.vehicles.filter(is_paid_off=False).aggregate(
                    total=Sum('balance')
                )['total'] or Decimal('0.00')

                has_unpaid_vehicle = client.vehicles.filter(is_paid_off=False).exists()
                has_any_vehicle = client.vehicles.exists()

                expected_status = client.status
                if has_any_vehicle and not has_unpaid_vehicle:
                    expected_status = 'completed'
                elif client.status == 'completed' and has_unpaid_vehicle:
                    expected_status = 'active'

                client_changed = (
                    client.current_debt != expected_debt
                    or client.status != expected_status
                )

                if client_changed:
                    client.current_debt = expected_debt
                    client.status = expected_status
                    client.save(update_fields=['current_debt', 'status'])
                    updated_clients += 1

        if dry_run:
            with transaction.atomic():
                recalc()
                transaction.set_rollback(True)
        else:
            recalc()

        mode_label = 'DRY-RUN' if dry_run else 'APPLIED'
        self.stdout.write(self.style.SUCCESS(f'Balance recalculation {mode_label} complete.'))
        self.stdout.write(f'Client vehicles processed: {processed_vehicles}')
        self.stdout.write(f'Client vehicles updated: {updated_vehicles}')
        self.stdout.write(f'Clients updated: {updated_clients}')
