"""
Register a company whose schema already holds data — used when moving an
existing deployment onto the platform (see docs/multi-company.md):

    python manage.py register_company --schema hoza --name "Hoza Investment (K) Limited" \\
        --domain hozacars.com --domain www.hozacars.com

The first --domain becomes the main address. Nothing is created or
migrated in the schema itself; run `migrate_schemas --schema=<name>`
afterwards to bring it up to date.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.tenancy.models import Company, Domain


class Command(BaseCommand):
    help = 'Register an existing schema as a company with its web addresses.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--domain', action='append', required=True, dest='domains')
        parser.add_argument('--country', default='KE')

    def handle(self, *args, **opts):
        if not settings.MULTI_TENANT:
            raise CommandError('Set MULTI_TENANT=True first.')
        schema = opts['schema']
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM information_schema.schemata WHERE schema_name = %s', [schema])
            if cursor.fetchone() is None:
                raise CommandError(f'Schema "{schema}" does not exist.')

        company, created = Company.objects.get_or_create(
            schema_name=schema,
            defaults={'name': opts['name'], 'country': opts['country'], 'status': Company.STATUS_ACTIVE,
                      'progress': 'Ready', 'created_by': 'register_company'},
        )
        for index, domain in enumerate(opts['domains']):
            Domain.objects.update_or_create(domain=domain.lower(),
                                            defaults={'tenant': company, 'is_primary': index == 0})
        self.stdout.write(self.style.SUCCESS(
            f'{"Registered" if created else "Updated"} {company.name} ({schema}) on {", ".join(opts["domains"])}'))
