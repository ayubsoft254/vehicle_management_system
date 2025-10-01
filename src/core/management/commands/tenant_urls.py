from django.core.management.base import BaseCommand
from core.models import Client, Domain


class Command(BaseCommand):
    help = 'Show how to access your tenants with proper domain mapping'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== TENANT ACCESS GUIDE ===\n'))
        
        tenants = Client.objects.all().order_by('schema_name')
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No tenants found!'))
            return
        
        self.stdout.write(self.style.SUCCESS('To access your tenants, use these URLs:\n'))
        
        for tenant in tenants:
            domains = tenant.domains.all()
            
            if tenant.schema_name == 'public':
                self.stdout.write(self.style.WARNING(f'🌐 PUBLIC SCHEMA (Shared):'))
                self.stdout.write(f'   Company: {tenant.company_name}')
                for domain in domains:
                    self.stdout.write(f'   📍 http://{domain.domain}:8000/')
                    self.stdout.write(f'   📍 http://{domain.domain}:8000/admin/')
                self.stdout.write('')
            else:
                self.stdout.write(self.style.SUCCESS(f'🏢 TENANT: {tenant.name}'))
                self.stdout.write(f'   Company: {tenant.company_name}')
                self.stdout.write(f'   Schema: {tenant.schema_name}')
                
                for domain in domains:
                    # For development, we need to modify hosts file or use localhost with different ports
                    # or use subdomain approach
                    self.stdout.write(f'   📍 http://{domain.domain}:8000/')
                    self.stdout.write(f'   📍 http://{domain.domain}:8000/admin/')
                self.stdout.write('')
        
        self.stdout.write(self.style.WARNING('IMPORTANT NOTES FOR DEVELOPMENT:'))
        self.stdout.write('1. For local development, you have a few options:')
        self.stdout.write('   a) Add entries to your hosts file (C:\\Windows\\System32\\drivers\\etc\\hosts):')
        for tenant in tenants:
            for domain in tenant.domains.all():
                if domain.domain != 'localhost':
                    self.stdout.write(f'      127.0.0.1 {domain.domain}')
        self.stdout.write('')
        self.stdout.write('   b) Use localhost subdomains (requires DNS setup):')
        for tenant in tenants:
            for domain in tenant.domains.all():
                if domain.domain != 'localhost':
                    self.stdout.write(f'      http://{domain.domain}.localhost:8000/')
        self.stdout.write('')
        self.stdout.write('2. Make sure to run: python manage.py runserver 0.0.0.0:8000')
        self.stdout.write('3. Each tenant has its own database schema and data')
        self.stdout.write('')
        self.stdout.write('='*60)