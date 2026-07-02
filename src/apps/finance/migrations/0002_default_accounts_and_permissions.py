"""
Data migration: default financial accounts + FINANCE module RolePermission rows.
"""
from decimal import Decimal

from django.db import migrations


DEFAULT_ACCOUNTS = [
    {
        'name': 'Financial Analyst Equity Hoza',
        'code': 'EQTY-HOZA',
        'account_type': 'bank',
    },
    {
        'name': 'DIB Hoza',
        'code': 'DIB-HOZA',
        'account_type': 'bank',
    },
    {
        'name': 'COOP Hoza',
        'code': 'COOP-HOZA',
        'account_type': 'bank',
    },
    {
        'name': 'Suspense Account - Hoza',
        'code': 'SUSPENSE-HOZA',
        'account_type': 'suspense',
    },
]

# role -> access_level for the FINANCE module
FINANCE_ROLE_ACCESS = {
    'admin': 'full_access',
    'manager': 'full_access',
    'accountant': 'full_access',
    'sales': 'no_access',
    'auctioneer': 'no_access',
    'clerk': 'read_only',
    'client': 'no_access',
    'auditor': 'read_only',
}

FINANCE_ROLE_FLAGS = {
    'admin': {'can_create': True, 'can_edit': True, 'can_delete': True, 'can_export': True},
    'manager': {'can_create': True, 'can_edit': True, 'can_delete': False, 'can_export': True},
    'accountant': {'can_create': True, 'can_edit': True, 'can_delete': False, 'can_export': True},
    'sales': {'can_create': False, 'can_edit': False, 'can_delete': False, 'can_export': False},
    'auctioneer': {'can_create': False, 'can_edit': False, 'can_delete': False, 'can_export': False},
    'clerk': {'can_create': False, 'can_edit': False, 'can_delete': False, 'can_export': False},
    'client': {'can_create': False, 'can_edit': False, 'can_delete': False, 'can_export': False},
    'auditor': {'can_create': False, 'can_edit': False, 'can_delete': False, 'can_export': True},
}


def create_default_accounts(apps, schema_editor):
    FinancialAccount = apps.get_model('finance', 'FinancialAccount')
    for data in DEFAULT_ACCOUNTS:
        FinancialAccount.objects.get_or_create(
            code=data['code'],
            defaults={
                'name': data['name'],
                'account_type': data['account_type'],
                'currency': 'KES',
                'opening_balance': Decimal('0.00'),
                'status': 'active',
                'is_default': data['account_type'] == 'bank',
                'allow_manual_transactions': True,
                'require_approval': True,
            }
        )


def remove_default_accounts(apps, schema_editor):
    FinancialAccount = apps.get_model('finance', 'FinancialAccount')
    FinancialAccount.objects.filter(code__in=[d['code'] for d in DEFAULT_ACCOUNTS]).delete()


def create_finance_role_permissions(apps, schema_editor):
    RolePermission = apps.get_model('permissions', 'RolePermission')
    for role, access_level in FINANCE_ROLE_ACCESS.items():
        flags = FINANCE_ROLE_FLAGS[role]
        RolePermission.objects.get_or_create(
            role=role,
            module_name='finance',
            defaults={
                'access_level': access_level,
                'can_create': flags['can_create'],
                'can_edit': flags['can_edit'],
                'can_delete': flags['can_delete'],
                'can_export': flags['can_export'],
                'is_active': True,
                'description': 'Auto-created by finance module setup',
            }
        )


def remove_finance_role_permissions(apps, schema_editor):
    RolePermission = apps.get_model('permissions', 'RolePermission')
    RolePermission.objects.filter(module_name='finance').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
        ('permissions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_accounts, remove_default_accounts),
        migrations.RunPython(create_finance_role_permissions, remove_finance_role_permissions),
    ]
