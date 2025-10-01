from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Client, Domain


class Command(BaseCommand):
    help = 'Create a new tenant with domain mapping'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help='Tenant name')
        parser.add_argument('--schema', type=str, required=True, help='Schema name (lowercase, no spaces)')
        parser.add_argument('--domain', type=str, required=True, help='Domain name for the tenant')
        parser.add_argument('--company-name', type=str, help='Company name')
        parser.add_argument('--company-email', type=str, help='Company email')
        parser.add_argument('--company-phone', type=str, help='Company phone')

    def handle(self, *args, **options):
        name = options['name']
        schema_name = options['schema'].lower().replace(' ', '_')
        domain_name = options['domain']
        company_name = options.get('company_name', name)
        company_email = options.get('company_email', f'admin@{domain_name}')
        company_phone = options.get('company_phone', '+1234567890')
        
        try:
            with transaction.atomic():
                # Check if tenant already exists
                if Client.objects.filter(schema_name=schema_name).exists():
                    self.stdout.write(
                        self.style.ERROR(f'Tenant with schema "{schema_name}" already exists!')
                    )
                    return
                
                # Check if domain already exists
                if Domain.objects.filter(domain=domain_name).exists():
                    self.stdout.write(
                        self.style.ERROR(f'Domain "{domain_name}" already exists!')
                    )
                    return
                
                # Create tenant
                tenant = Client.objects.create(
                    schema_name=schema_name,
                    name=name,
                    company_name=company_name,
                    company_email=company_email,
                    company_phone=company_phone
                )
                
                # Create domain for tenant
                Domain.objects.create(
                    domain=domain_name,
                    tenant=tenant,
                    is_primary=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created tenant "{name}" with domain "{domain_name}"'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Schema: {schema_name}'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating tenant: {str(e)}')
            )