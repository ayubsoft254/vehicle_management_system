from django.core.management.base import BaseCommand
from core.models import Client, Domain


class Command(BaseCommand):
    help = 'List all tenants and their domains'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== TENANTS AND DOMAINS ==='))
        
        tenants = Client.objects.all().order_by('schema_name')
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No tenants found!'))
            self.stdout.write('Run "python manage.py create_public_tenant" first to create the public tenant.')
            return
        
        for tenant in tenants:
            self.stdout.write(f'\nTenant: {tenant.name}')
            self.stdout.write(f'  Schema: {tenant.schema_name}')
            self.stdout.write(f'  Company: {tenant.company_name}')
            self.stdout.write(f'  Email: {tenant.company_email}')
            self.stdout.write(f'  Active: {tenant.is_active}')
            
            domains = tenant.domains.all()
            if domains:
                self.stdout.write('  Domains:')
                for domain in domains:
                    primary = ' (PRIMARY)' if domain.is_primary else ''
                    self.stdout.write(f'    - {domain.domain}{primary}')
            else:
                self.stdout.write(self.style.WARNING('    No domains configured!'))
        
        self.stdout.write('\n' + '='*50)