"""
Management command to initialize role permissions
Sets up default permissions for all user roles in the system
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.permissions.models import RolePermission
from utils.constants import UserRole, ModuleName, AccessLevel


class Command(BaseCommand):
    help = 'Initialize default permissions for all user roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing permissions and recreate them',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Initialize permissions for specific role only',
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        specific_role = options.get('role')

        if reset:
            self.stdout.write(self.style.WARNING('Deleting existing permissions...'))
            RolePermission.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('All permissions deleted.'))

        self.stdout.write(self.style.WARNING('Initializing permissions...'))
        
        with transaction.atomic():
            created_count = self.create_permissions(specific_role)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} permissions!'
            )
        )

    def create_permissions(self, specific_role=None):
        """Create default permissions for all roles"""
        
        # Define permission profiles for each role
        permission_profiles = {
            # ============ ADMIN - Full access to everything ============
            UserRole.ADMIN: {
                'default': {
                    'access_level': AccessLevel.FULL_ACCESS,
                    'can_create': True,
                    'can_edit': True,
                    'can_delete': True,
                    'can_export': True,
                },
                'modules': {}  # No overrides - full access to all
            },
            
            # ============ MANAGER - Full access except some admin functions ============
            UserRole.MANAGER: {
                'default': {
                    'access_level': AccessLevel.FULL_ACCESS,
                    'can_create': True,
                    'can_edit': True,
                    'can_delete': True,
                    'can_export': True,
                },
                'modules': {
                    ModuleName.PERMISSIONS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_create': False,
                        'can_edit': False,
                        'can_delete': False,
                    },
                }
            },
            
            # ============ SALES - Access to vehicles, clients, payments ============
            UserRole.SALES: {
                'default': {
                    'access_level': AccessLevel.NO_ACCESS,
                    'can_create': False,
                    'can_edit': False,
                    'can_delete': False,
                    'can_export': False,
                },
                'modules': {
                    ModuleName.DASHBOARD: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.VEHICLES: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.CLIENTS: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.PAYMENTS: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.INSURANCE: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.DOCUMENTS: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': False,
                        'can_export': True,
                    },
                    ModuleName.REPORTS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                }
            },
            
            # ============ ACCOUNTANT - Access to financial modules ============
            UserRole.ACCOUNTANT: {
                'default': {
                    'access_level': AccessLevel.NO_ACCESS,
                    'can_create': False,
                    'can_edit': False,
                    'can_delete': False,
                    'can_export': False,
                },
                'modules': {
                    ModuleName.DASHBOARD: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.PAYMENTS: {
                        'access_level': AccessLevel.FULL_ACCESS,
                        'can_create': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_export': True,
                    },
                    ModuleName.PAYROLL: {
                        'access_level': AccessLevel.FULL_ACCESS,
                        'can_create': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_export': True,
                    },
                    ModuleName.EXPENSES: {
                        'access_level': AccessLevel.FULL_ACCESS,
                        'can_create': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_export': True,
                    },
                    ModuleName.REPORTS: {
                        'access_level': AccessLevel.FULL_ACCESS,
                        'can_export': True,
                    },
                    ModuleName.CLIENTS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.VEHICLES: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.REPOSSESSIONS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.AUCTIONS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.AUDIT: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                }
            },
            
            # ============ AUCTIONEER - Access to auctions and repossessions ============
            UserRole.AUCTIONEER: {
                'default': {
                    'access_level': AccessLevel.NO_ACCESS,
                    'can_create': False,
                    'can_edit': False,
                    'can_delete': False,
                    'can_export': False,
                },
                'modules': {
                    ModuleName.DASHBOARD: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.AUCTIONS: {
                        'access_level': AccessLevel.FULL_ACCESS,
                        'can_create': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_export': True,
                    },
                    ModuleName.REPOSSESSIONS: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.VEHICLES: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.CLIENTS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                    ModuleName.DOCUMENTS: {
                        'access_level': AccessLevel.READ_WRITE,
                        'can_create': True,
                        'can_edit': True,
                        'can_export': True,
                    },
                    ModuleName.REPORTS: {
                        'access_level': AccessLevel.READ_ONLY,
                        'can_export': True,
                    },
                }
            },
            
            # ============ CLERK - Read only access ============
            UserRole.CLERK: {
                'default': {
                    'access_level': AccessLevel.NO_ACCESS,
                    'can_create': False,
                    'can_edit': False,
                    'can_delete': False,
                    'can_export': False,
                },
                'modules': {
                    ModuleName.DASHBOARD: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                    ModuleName.VEHICLES: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                    ModuleName.CLIENTS: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                    ModuleName.PAYMENTS: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                    ModuleName.DOCUMENTS: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                    ModuleName.INSURANCE: {
                        'access_level': AccessLevel.READ_ONLY,
                    },
                }
            },
            
            # ============ CLIENT - Portal access only ============
            UserRole.CLIENT: {
                'default': {
                    'access_level': AccessLevel.NO_ACCESS,
                    'can_create': False,
                    'can_edit': False,
                    'can_delete': False,
                    'can_export': False,
                },
                'modules': {
                    # Clients have no access to staff modules
                    # They use their own portal at /clients/portal/
                }
            },
        }

        created_count = 0
        
        # Determine which roles to process
        if specific_role:
            if specific_role not in [r[0] for r in UserRole.CHOICES]:
                self.stdout.write(
                    self.style.ERROR(f'Invalid role: {specific_role}')
                )
                return 0
            roles_to_process = [specific_role]
        else:
            roles_to_process = [r[0] for r in UserRole.CHOICES]

        for role in roles_to_process:
            if role not in permission_profiles:
                self.stdout.write(
                    self.style.WARNING(f'No permission profile for role: {role}')
                )
                continue

            profile = permission_profiles[role]
            defaults_config = profile['default']
            module_overrides = profile['modules']

            self.stdout.write(f'\nProcessing role: {dict(UserRole.CHOICES)[role]}')

            for module in [m[0] for m in ModuleName.CHOICES]:
                # Check if there's a specific override for this module
                if module in module_overrides:
                    config = {**defaults_config, **module_overrides[module]}
                else:
                    config = defaults_config

                # Create or update permission
                permission, created = RolePermission.objects.update_or_create(
                    role=role,
                    module_name=module,
                    defaults={
                        'access_level': config['access_level'],
                        'can_create': config.get('can_create', False),
                        'can_edit': config.get('can_edit', False),
                        'can_delete': config.get('can_delete', False),
                        'can_export': config.get('can_export', False),
                        'is_active': True,
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Created: {module} - {config["access_level"]}'
                        )
                    )
                else:
                    self.stdout.write(
                        f'  ↻ Updated: {module} - {config["access_level"]}'
                    )

        return created_count
