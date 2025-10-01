from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Client, Domain


class Command(BaseCommand):
    help = 'Create the public tenant required by django-tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            default='localhost',
            help='Domain for the public tenant (default: localhost)'
        )
        parser.add_argument(
            '--schema',
            type=str,
            default='public',
            help='Schema name for the public tenant (default: public)'
        )

    def handle(self, *args, **options):
        domain_name = options['domain']
        schema_name = options['schema']
        
        try:
            with transaction.atomic():
                # Check if public tenant already exists
                if Client.objects.filter(schema_name=schema_name).exists():
                    self.stdout.write(
                        self.style.WARNING(f'Public tenant with schema "{schema_name}" already exists!')
                    )
                    return
                
                # Create public tenant
                public_tenant = Client.objects.create(
                    schema_name=schema_name,
                    name='Public Tenant',
                    company_name='Vehicle Management System',
                    company_email='admin@example.com',
                    company_phone='+1234567890'
                )
                
                # Create domain for public tenant
                Domain.objects.create(
                    domain=domain_name,
                    tenant=public_tenant,
                    is_primary=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created public tenant with domain "{domain_name}"'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating public tenant: {str(e)}')
            )