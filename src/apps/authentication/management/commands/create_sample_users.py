"""
Management command to create sample user profiles for testing role-based access
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.authentication.models import UserProfile
from utils.constants import UserRole
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample user profiles for testing different role permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing sample users before creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample user profiles...'))

        if options['reset']:
            self.stdout.write('Deleting existing sample users...')
            User.objects.filter(email__endswith='@sample.test').delete()
            self.stdout.write(self.style.SUCCESS('Existing sample users deleted.'))

        sample_users = [
            {
                'email': 'admin@sample.test',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': UserRole.ADMIN,
                'phone': '+254700000001',
                'employee_id': 'EMP-ADM-001',
                'department': 'Administration',
                'password': 'admin123',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'email': 'manager@sample.test',
                'first_name': 'John',
                'last_name': 'Manager',
                'role': UserRole.MANAGER,
                'phone': '+254700000002',
                'employee_id': 'EMP-MGR-001',
                'department': 'Management',
                'password': 'manager123',
                'address': '123 Manager Street, Nairobi',
                'city': 'Nairobi',
            },
            {
                'email': 'sales@sample.test',
                'first_name': 'Jane',
                'last_name': 'Sales',
                'role': UserRole.SALES,
                'phone': '+254700000003',
                'employee_id': 'EMP-SAL-001',
                'department': 'Sales',
                'password': 'sales123',
                'address': '456 Sales Avenue, Nairobi',
                'city': 'Nairobi',
            },
            {
                'email': 'accountant@sample.test',
                'first_name': 'Michael',
                'last_name': 'Accountant',
                'role': UserRole.ACCOUNTANT,
                'phone': '+254700000004',
                'employee_id': 'EMP-ACC-001',
                'department': 'Finance',
                'password': 'accountant123',
                'address': '789 Finance Road, Nairobi',
                'city': 'Nairobi',
            },
            {
                'email': 'auctioneer@sample.test',
                'first_name': 'Sarah',
                'last_name': 'Auctioneer',
                'role': UserRole.AUCTIONEER,
                'phone': '+254700000005',
                'employee_id': 'EMP-AUC-001',
                'department': 'Auctions',
                'password': 'auctioneer123',
                'address': '321 Auction Place, Nairobi',
                'city': 'Nairobi',
            },
            {
                'email': 'clerk@sample.test',
                'first_name': 'David',
                'last_name': 'Clerk',
                'role': UserRole.CLERK,
                'phone': '+254700000006',
                'employee_id': 'EMP-CLK-001',
                'department': 'Administration',
                'password': 'clerk123',
                'address': '654 Office Lane, Nairobi',
                'city': 'Nairobi',
            },
        ]

        created_users = []

        for user_data in sample_users:
            password = user_data.pop('password')
            email = user_data['email']

            try:
                user, created = User.objects.update_or_create(
                    email=email,
                    defaults={
                        **user_data,
                        'is_active': True,
                        'hire_date': timezone.now().date() - timedelta(days=180),
                    }
                )

                if created:
                    user.set_password(password)
                    user.save()

                    # Create user profile
                    UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'bio': f'{user.first_name} is a {user.get_role_display()} in the vehicle management system.',
                            'email_notifications': True,
                            'sms_notifications': True,
                            'emergency_contact_name': f'{user.first_name} Emergency Contact',
                            'emergency_contact_phone': '+254711111111',
                            'emergency_contact_relationship': 'Family',
                        }
                    )

                    created_users.append(user)
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created user: {user.email} ({user.get_role_display()})')
                    )
                else:
                    # Update password for existing user
                    user.set_password(password)
                    user.save()
                    self.stdout.write(
                        self.style.WARNING(f'⚠ Updated existing user: {user.email} ({user.get_role_display()})')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error creating user {email}: {str(e)}')
                )

        # Display summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'Successfully created/updated {len(created_users)} sample users!'))
        self.stdout.write('=' * 80 + '\n')

        self.stdout.write(self.style.SUCCESS('Login Credentials:'))
        self.stdout.write('-' * 80)

        for user_data in sample_users:
            role_display = dict(UserRole.CHOICES)[user_data['role']]
            self.stdout.write(
                f"  {role_display:20} | Email: {user_data['email']:30} | Password: {user_data.get('password', 'N/A')}"
            )

        self.stdout.write('-' * 80)
        self.stdout.write('\n' + self.style.SUCCESS('You can now login with any of these accounts to test permissions!'))
        self.stdout.write(self.style.WARNING('Note: These are test accounts. Use strong passwords in production.\n'))
