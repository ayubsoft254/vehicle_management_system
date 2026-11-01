"""
Run (or re-run) a company's setup synchronously, e.g. when no Celery worker
is available:  python manage.py provision_company acme
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.models import Company
from apps.tenancy.provisioning import provision


class Command(BaseCommand):
    help = "Create and seed a company's schema now."

    def add_arguments(self, parser):
        parser.add_argument('schema')

    def handle(self, *args, **opts):
        company = Company.objects.filter(schema_name=opts['schema']).first()
        if company is None:
            raise CommandError(f'No company with schema "{opts["schema"]}".')
        link = provision(company.pk)
        self.stdout.write(self.style.SUCCESS(f'{company.name} is ready.'))
        if link:
            self.stdout.write(f'Admin sign-in link: {link}')
