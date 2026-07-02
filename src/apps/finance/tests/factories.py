"""
Shared test fixtures for the finance app's test suite.

Deliberately not dependent on data migrations (default accounts, default
RolePermission rows) — MIGRATION_MODULES is disabled for test runs (see
config/settings.py) so tables are built straight from current model state
and data migrations never run. Every fixture needed by a test is created
here explicitly.
"""
from datetime import date
from decimal import Decimal

from apps.authentication.models import User
from apps.clients.models import Client, ClientVehicle
from apps.expenses.models import ExpenseCategory
from apps.finance.models import FinancialAccount
from apps.payments.models import InstallmentPlan
from apps.permissions.models import RolePermission
from apps.vehicles.models import Vehicle
from utils.constants import AccessLevel, ModuleName, UserRole


def make_user(email='user@test.com', role=UserRole.ADMIN, is_superuser=False):
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={'role': role, 'is_active': True, 'is_superuser': is_superuser, 'is_staff': is_superuser},
    )
    return user


def make_finance_permission(role, *, access_level=AccessLevel.FULL_ACCESS,
                             can_create=True, can_edit=True, can_delete=False, can_export=True):
    permission, _ = RolePermission.objects.update_or_create(
        role=role, module_name=ModuleName.FINANCE,
        defaults={
            'access_level': access_level, 'can_create': can_create, 'can_edit': can_edit,
            'can_delete': can_delete, 'can_export': can_export, 'is_active': True,
        },
    )
    return permission


def make_account(code='TEST-ACC', name='Test Account', account_type='bank',
                  require_approval=True, opening_balance=Decimal('0.00'), **kwargs):
    account, _ = FinancialAccount.objects.get_or_create(
        code=code,
        defaults={
            'name': name, 'account_type': account_type, 'currency': 'KES',
            'opening_balance': opening_balance, 'opening_balance_date': date(2026, 1, 1),
            'status': 'active', 'allow_manual_transactions': True,
            'require_approval': require_approval, **kwargs,
        },
    )
    return account


def make_client(id_number='TESTID001', first_name='Test', last_name='Client', registered_by=None):
    client, _ = Client.objects.get_or_create(
        id_number=id_number,
        defaults={
            'first_name': first_name, 'last_name': last_name,
            'phone_primary': '0700000000', 'registered_by': registered_by or make_user(),
        },
    )
    return client


def make_vehicle(vin='TESTVIN0000000001', registration_number='KTEST001', added_by=None):
    vehicle, _ = Vehicle.objects.get_or_create(
        vin=vin,
        defaults={
            'make': 'Toyota', 'model': 'Axio', 'year': 2015, 'color': 'White',
            'registration_number': registration_number, 'mileage': 50000,
            'purchase_price': Decimal('800000'), 'selling_price': Decimal('1200000'),
            'purchase_date': date(2026, 1, 1), 'added_by': added_by or make_user(),
        },
    )
    return vehicle


def make_client_vehicle(with_installment_plan=True, monthly_installment=Decimal('30000'),
                         number_of_installments=40, total_amount=Decimal('1200000'),
                         client_id_number='TESTID001', vehicle_vin='TESTVIN0000000001'):
    admin = make_user()
    client = make_client(id_number=client_id_number)
    vehicle = make_vehicle(vin=vehicle_vin, registration_number=f'K{vehicle_vin[-6:]}')
    client_vehicle, _ = ClientVehicle.objects.get_or_create(
        client=client, vehicle=vehicle,
        defaults={
            'purchase_date': date(2026, 1, 1), 'purchase_price': total_amount,
            'client_purchase_price': total_amount, 'final_selling_price': total_amount,
            'deposit_paid': Decimal('0'), 'total_paid': Decimal('0'), 'balance': total_amount,
            'monthly_installment': monthly_installment, 'installment_months': number_of_installments,
            'payment_type': 'installment',
        },
    )
    if with_installment_plan:
        plan, created = InstallmentPlan.objects.get_or_create(
            client_vehicle=client_vehicle,
            defaults={
                'total_amount': total_amount, 'deposit': Decimal('0'),
                'monthly_installment': monthly_installment, 'number_of_installments': number_of_installments,
                'start_date': date(2026, 1, 1), 'created_by': admin,
            },
        )
        if created:
            plan.generate_payment_schedule()
    return client_vehicle


def make_expense_category(name='Test Category', code='TESTCAT'):
    category, _ = ExpenseCategory.objects.get_or_create(name=name, defaults={'code': code})
    return category
