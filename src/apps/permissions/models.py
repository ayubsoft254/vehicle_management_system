"""
Permissions Models
Role-based module access control
"""
from django.db import models
from utils.constants import UserRole, ModuleName, AccessLevel


class RolePermission(models.Model):
    """
    Defines access level for each role per module
    Example: Sales role has READ_WRITE access to Vehicles module
    """
    role = models.CharField(
        'User Role',
        max_length=20,
        choices=UserRole.CHOICES,
        help_text='User role (admin, sales, etc.)'
    )
    
    module_name = models.CharField(
        'Module Name',
        max_length=50,
        choices=ModuleName.CHOICES,
        help_text='System module'
    )
    
    access_level = models.CharField(
        'Access Level',
        max_length=20,
        choices=AccessLevel.CHOICES,
        default=AccessLevel.NO_ACCESS,
        help_text='Level of access to this module'
    )
    
    # Additional settings
    can_create = models.BooleanField(
        'Can Create',
        default=False,
        help_text='Can create new records'
    )
    
    can_edit = models.BooleanField(
        'Can Edit',
        default=False,
        help_text='Can edit existing records'
    )
    
    can_delete = models.BooleanField(
        'Can Delete',
        default=False,
        help_text='Can delete records'
    )
    
    can_export = models.BooleanField(
        'Can Export',
        default=False,
        help_text='Can export data to PDF/Excel'
    )
    
    # Metadata
    description = models.TextField(
        'Description',
        blank=True,
        help_text='Optional description of this permission'
    )
    
    is_active = models.BooleanField(
        'Active',
        default=True,
        help_text='Whether this permission is active'
    )
    
    # Timestamps
    created_at = models.DateTimeField('Created At', auto_now_add=True)
    updated_at = models.DateTimeField('Updated At', auto_now=True)
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permissions_created'
    )
    
    class Meta:
        db_table = 'role_permissions'
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
        unique_together = ['role', 'module_name']
        ordering = ['role', 'module_name']
        indexes = [
            models.Index(fields=['role', 'module_name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_role_display()} - {self.get_module_name_display()}: {self.get_access_level_display()}"
    
    def has_access(self):
        """Check if role has any access to module"""
        return self.is_active and self.access_level != AccessLevel.NO_ACCESS
    
    def can_view(self):
        """Check if role can view module"""
        return self.has_access()
    
    def can_modify(self):
        """Check if role can modify (create/edit/delete)"""
        return self.access_level in [AccessLevel.READ_WRITE, AccessLevel.FULL_ACCESS]
    
    def has_full_control(self):
        """Check if role has full access"""
        return self.access_level == AccessLevel.FULL_ACCESS
    
    @classmethod
    def get_user_permissions(cls, user):
        """Get all permissions for a user based on their role"""
        if user.is_superuser:
            # Superusers have full access to everything
            return cls.objects.all()
        return cls.objects.filter(role=user.role, is_active=True)
    
    @classmethod
    def user_can_access_module(cls, user, module_name):
        """Check if user can access a specific module"""
        if user.is_superuser:
            return True
        
        try:
            permission = cls.objects.get(
                role=user.role,
                module_name=module_name,
                is_active=True
            )
            return permission.has_access()
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def initialize_default_permissions(cls):
        """
        Create default permissions for all roles and modules
        Call this after migrations
        """
        default_permissions = {
            # Admin - Full access to everything
            UserRole.ADMIN: {
                'access_level': AccessLevel.FULL_ACCESS,
                'can_create': True,
                'can_edit': True,
                'can_delete': True,
                'can_export': True,
            },
            # Manager - Full access except some admin functions
            UserRole.MANAGER: {
                'access_level': AccessLevel.FULL_ACCESS,
                'can_create': True,
                'can_edit': True,
                'can_delete': False,
                'can_export': True,
            },
            # Sales - Access to vehicles, clients, payments
            UserRole.SALES: {
                'access_level': AccessLevel.READ_WRITE,
                'can_create': True,
                'can_edit': True,
                'can_delete': False,
                'can_export': True,
            },
            # Accountant - Access to financial modules
            UserRole.ACCOUNTANT: {
                'access_level': AccessLevel.READ_WRITE,
                'can_create': True,
                'can_edit': True,
                'can_delete': False,
                'can_export': True,
            },
            # Auctioneer - Access to auctions and repossessions
            UserRole.AUCTIONEER: {
                'access_level': AccessLevel.READ_WRITE,
                'can_create': True,
                'can_edit': True,
                'can_delete': False,
                'can_export': True,
            },
            # Clerk - Read only access
            UserRole.CLERK: {
                'access_level': AccessLevel.READ_ONLY,
                'can_create': False,
                'can_edit': False,
                'can_delete': False,
                'can_export': False,
            },
        }
        
        # Module specific overrides for specific roles
        role_module_overrides = {
            UserRole.SALES: {
                ModuleName.VEHICLES: AccessLevel.READ_WRITE,
                ModuleName.CLIENTS: AccessLevel.READ_WRITE,
                ModuleName.PAYMENTS: AccessLevel.READ_WRITE,
                ModuleName.INSURANCE: AccessLevel.READ_WRITE,
                ModuleName.DOCUMENTS: AccessLevel.READ_WRITE,
                ModuleName.PAYROLL: AccessLevel.NO_ACCESS,
                ModuleName.AUDIT: AccessLevel.NO_ACCESS,
                ModuleName.PERMISSIONS: AccessLevel.NO_ACCESS,
            },
            UserRole.ACCOUNTANT: {
                ModuleName.PAYMENTS: AccessLevel.FULL_ACCESS,
                ModuleName.PAYROLL: AccessLevel.FULL_ACCESS,
                ModuleName.EXPENSES: AccessLevel.FULL_ACCESS,
                ModuleName.REPORTS: AccessLevel.FULL_ACCESS,
                ModuleName.REPOSSESSIONS: AccessLevel.READ_ONLY,
                ModuleName.AUCTIONS: AccessLevel.READ_ONLY,
                ModuleName.PERMISSIONS: AccessLevel.NO_ACCESS,
            },
            UserRole.AUCTIONEER: {
                ModuleName.AUCTIONS: AccessLevel.FULL_ACCESS,
                ModuleName.REPOSSESSIONS: AccessLevel.READ_WRITE,
                ModuleName.VEHICLES: AccessLevel.READ_ONLY,
                ModuleName.PAYROLL: AccessLevel.NO_ACCESS,
                ModuleName.PERMISSIONS: AccessLevel.NO_ACCESS,
            },
            UserRole.CLERK: {
                ModuleName.DASHBOARD: AccessLevel.READ_ONLY,
                ModuleName.VEHICLES: AccessLevel.READ_ONLY,
                ModuleName.CLIENTS: AccessLevel.READ_ONLY,
                ModuleName.DOCUMENTS: AccessLevel.READ_ONLY,
            },
        }
        
        created_count = 0
        
        for role in [r[0] for r in UserRole.CHOICES]:
            defaults = default_permissions.get(role, {
                'access_level': AccessLevel.NO_ACCESS,
                'can_create': False,
                'can_edit': False,
                'can_delete': False,
                'can_export': False,
            })
            
            for module in [m[0] for m in ModuleName.CHOICES]:
                # Check for role-specific override
                if role in role_module_overrides and module in role_module_overrides[role]:
                    access_level = role_module_overrides[role][module]
                else:
                    access_level = defaults['access_level']
                
                permission, created = cls.objects.get_or_create(
                    role=role,
                    module_name=module,
                    defaults={
                        'access_level': access_level,
                        'can_create': defaults['can_create'] if access_level != AccessLevel.NO_ACCESS else False,
                        'can_edit': defaults['can_edit'] if access_level != AccessLevel.NO_ACCESS else False,
                        'can_delete': defaults['can_delete'] if access_level != AccessLevel.NO_ACCESS else False,
                        'can_export': defaults['can_export'] if access_level != AccessLevel.NO_ACCESS else False,
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
        
        return created_count


class PermissionHistory(models.Model):
    """
    Track permission changes for audit purposes
    """
    permission = models.ForeignKey(
        RolePermission,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    changed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='permission_changes'
    )
    
    action = models.CharField(
        'Action',
        max_length=20,
        choices=[
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('deleted', 'Deleted'),
            ('activated', 'Activated'),
            ('deactivated', 'Deactivated'),
        ]
    )
    
    old_value = models.JSONField(
        'Old Value',
        null=True,
        blank=True,
        help_text='Previous permission settings'
    )
    
    new_value = models.JSONField(
        'New Value',
        null=True,
        blank=True,
        help_text='New permission settings'
    )
    
    reason = models.TextField(
        'Reason',
        blank=True,
        help_text='Reason for change'
    )
    
    timestamp = models.DateTimeField('Timestamp', auto_now_add=True)
    
    class Meta:
        db_table = 'permission_history'
        verbose_name = 'Permission History'
        verbose_name_plural = 'Permission History'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.action.title()} - {self.permission} at {self.timestamp}"