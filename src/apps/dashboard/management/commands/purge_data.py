"""
Purge ALL business data, keeping only superuser accounts (and their profiles).

Deletes every row from the local apps (vehicles, clients, payments, payroll,
expenses, repossessions, auctions, insurance, notifications, documents,
reports, audit, permissions, dashboard, assistant), all non-superuser user
accounts, the admin action log, and all sessions (everyone gets logged out).

Keeps: superusers + their UserProfile rows, groups/permissions/content types,
sites, celery-beat schedules, and allauth social-app config. Uploaded media
files are NOT touched — they become orphans on disk.

Runs as a DRY RUN by default (prints counts, rolls everything back).
Pass --commit to actually delete:

    python manage.py purge_data           # dry run
    python manage.py purge_data --commit  # the real thing
"""
from collections import Counter

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError

from apps.authentication.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = ('Delete all business data and non-superuser accounts, keeping only '
            'superusers. Dry run by default; pass --commit to actually delete.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit', action='store_true',
            help='actually delete (default is a dry run that rolls back)',
        )

    def handle(self, *args, **options):
        commit = options['commit']

        db = settings.DATABASES['default']
        self.stdout.write(
            f"Database: engine={db['ENGINE'].rsplit('.', 1)[-1]} "
            f"name={db.get('NAME')} host={db.get('HOST') or 'local'}"
        )
        keepers = list(User.objects.filter(is_superuser=True)
                       .values_list('email', flat=True))
        if not keepers:
            raise CommandError('Refusing to run: no superuser account exists to keep.')
        self.stdout.write(f"Keeping superusers: {', '.join(keepers)}")
        self.stdout.write(
            f"Mode: {'COMMIT — data will be deleted' if commit else 'DRY RUN'}\n"
        )

        local_labels = {ac.label for ac in django_apps.get_app_configs()
                        if ac.name.startswith('apps.')}
        pending = [m for m in django_apps.get_models()
                   if m._meta.app_label in local_labels
                   and m not in (User, UserProfile)
                   and not m._meta.proxy]
        pending += [LogEntry, Session]

        grand = Counter()
        with transaction.atomic():
            # PROTECT relationships dictate deletion order; instead of
            # hardcoding it, retry blocked models each pass until none remain.
            pass_no = 0
            while pending:
                pass_no += 1
                blocked = []
                for model in pending:
                    try:
                        with transaction.atomic():
                            total, detail = model.objects.all().delete()
                    except (ProtectedError, RestrictedError):
                        blocked.append(model)
                        continue
                    if total:
                        self.stdout.write(
                            f"[pass {pass_no}] {model._meta.label}: {total} rows"
                        )
                        grand.update(detail)
                if blocked and len(blocked) == len(pending):
                    names = ', '.join(m._meta.label for m in blocked)
                    raise CommandError(f'Deadlock: still PROTECT-blocked: {names}')
                pending = blocked

            total, detail = User.objects.filter(is_superuser=False).delete()
            if total:
                self.stdout.write(f"non-superuser accounts: {total} rows")
                grand.update(detail)

            self.stdout.write(f"\nTotal rows deleted: {sum(grand.values())}")
            for label, count in sorted(grand.items()):
                self.stdout.write(f"   {label}: {count}")

            if not commit:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(
                    '\nDRY RUN — everything rolled back. '
                    'Re-run with --commit to purge.'
                ))
            else:
                self.stdout.write(self.style.SUCCESS('\nCOMMITTED.'))
