"""
One-time platform setup after `migrate_schemas --shared`: register the
platform (public schema) on PLATFORM_DOMAIN and create a platform owner.

    python manage.py setup_platform --owner-email you@example.com
"""
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.tenancy.models import Company, Domain


class Command(BaseCommand):
    help = 'Register the platform domain and create a platform-owner account.'

    def add_arguments(self, parser):
        parser.add_argument('--domain', default=settings.PLATFORM_DOMAIN,
                            help='Control panel address (default: PLATFORM_DOMAIN)')
        parser.add_argument('--owner-email', help='Platform owner to create (skipped if omitted)')
        parser.add_argument('--owner-password', help='Defaults to a random password, printed once')

    def handle(self, *args, **opts):
        if not settings.MULTI_TENANT:
            raise CommandError('Set MULTI_TENANT=True first.')
        with schema_context('public'):
            platform, created = Company.objects.get_or_create(
                schema_name='public',
                defaults={'name': settings.PLATFORM_NAME, 'status': Company.STATUS_ACTIVE, 'progress': 'Platform'},
            )
            Domain.objects.get_or_create(domain=opts['domain'], defaults={'tenant': platform, 'is_primary': True})
            self.stdout.write(f'Platform {"registered" if created else "already registered"} on {opts["domain"]}')

            if opts['owner_email']:
                from apps.authentication.models import User
                password = opts['owner_password'] or secrets.token_urlsafe(14)
                user = User.objects.filter(email__iexact=opts['owner_email']).first()
                if user:
                    self.stdout.write(f'Owner {user.email} already exists (password unchanged)')
                else:
                    User.objects.create_superuser(email=opts['owner_email'], password=password)
                    self.stdout.write(self.style.SUCCESS(f'Created platform owner {opts["owner_email"]}'))
                    if not opts['owner_password']:
                        self.stdout.write(f'Password (shown once): {password}')
