"""
Expire stale proformas, warn about reservations nearing expiry and flag
expired reservations for manager review.

Run daily (cron / Celery beat):
    python manage.py check_reservations
"""
from django.core.management.base import BaseCommand

from apps.clients.reservation_services import process_reservations


class Command(BaseCommand):
    help = 'Process proforma/reservation expiry and send expiry notifications.'

    def handle(self, *args, **options):
        process_reservations()
        self.stdout.write(self.style.SUCCESS('Reservation check complete.'))
