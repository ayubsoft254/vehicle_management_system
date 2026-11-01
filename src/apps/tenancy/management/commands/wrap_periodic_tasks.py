"""
Celery beat runs on the platform schema, so a periodic task scheduled as
"apps.notifications.tasks.send_reminders" would only ever see the platform.
This rewrites every periodic task to go through run_for_all_companies, which
sends it once per active company in that company's schema. Idempotent.

    python manage.py wrap_periodic_tasks          # apply
    python manage.py wrap_periodic_tasks --dry-run
"""
import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask

FANOUT = 'apps.tenancy.tasks.run_for_all_companies'
SKIP = {FANOUT, 'celery.backend_cleanup'}


class Command(BaseCommand):
    help = 'Make every periodic task run once per company.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        changed = 0
        for task in PeriodicTask.objects.exclude(task__in=SKIP):
            original_args = json.loads(task.args or '[]')
            original_kwargs = json.loads(task.kwargs or '{}')
            self.stdout.write(f'{task.name}: {task.task} -> per company')
            if not opts['dry_run']:
                task.args = json.dumps([task.task, original_args, original_kwargs])
                task.kwargs = '{}'
                task.task = FANOUT
                task.save()
            changed += 1
        self.stdout.write(self.style.SUCCESS(f'{changed} periodic task(s) {"would be " if opts["dry_run"] else ""}wrapped.'))
