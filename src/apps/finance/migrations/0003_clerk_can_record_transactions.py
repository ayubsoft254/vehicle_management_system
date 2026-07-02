"""
Data migration: give the Clerk (Cashier) role permission to record finance
transactions (e.g. client payments) while still being unable to approve or
edit them, matching spec section 15's Cashier role definition.
"""
from django.db import migrations


def update_clerk_permission(apps, schema_editor):
    RolePermission = apps.get_model('permissions', 'RolePermission')
    RolePermission.objects.filter(role='clerk', module_name='finance').update(
        access_level='read_write',
        can_create=True,
        can_edit=False,
        can_delete=False,
        can_export=False,
    )


def revert_clerk_permission(apps, schema_editor):
    RolePermission = apps.get_model('permissions', 'RolePermission')
    RolePermission.objects.filter(role='clerk', module_name='finance').update(
        access_level='read_only',
        can_create=False,
        can_edit=False,
        can_delete=False,
        can_export=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_default_accounts_and_permissions'),
    ]

    operations = [
        migrations.RunPython(update_clerk_permission, revert_clerk_permission),
    ]
