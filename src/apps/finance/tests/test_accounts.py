"""
Covers spec Testing Requirements #1 (default accounts), #2 (account creation),
#3 (ledger opens), #16 (balances match ledger calculations).
"""
import importlib
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.finance import services
from apps.finance.models import FinancialAccount

from .factories import make_account, make_finance_permission, make_user


class DefaultAccountsMigrationTests(TestCase):
    """#1: Default accounts are created correctly.

    Data migrations don't run in the test DB (MIGRATION_MODULES is disabled
    for test runs — see config/settings.py), so this invokes the migration's
    own functions directly against real models, which is what actually
    verifies its behavior is correct.
    """

    def test_creates_four_default_accounts_and_role_permissions(self):
        migration = importlib.import_module(
            'apps.finance.migrations.0002_default_accounts_and_permissions'
        )
        from django.apps import apps as global_apps
        migration.create_default_accounts(global_apps, None)
        migration.create_finance_role_permissions(global_apps, None)

        accounts = {a.code: a for a in FinancialAccount.objects.all()}
        self.assertEqual(
            set(accounts.keys()),
            {'EQTY-HOZA', 'DIB-HOZA', 'COOP-HOZA', 'SUSPENSE-HOZA'},
        )
        for code in ('EQTY-HOZA', 'DIB-HOZA', 'COOP-HOZA'):
            self.assertEqual(accounts[code].account_type, 'bank')
            self.assertEqual(accounts[code].opening_balance, Decimal('0.00'))
            self.assertEqual(accounts[code].status, 'active')
            self.assertEqual(accounts[code].currency, 'KES')
        self.assertEqual(accounts['SUSPENSE-HOZA'].account_type, 'suspense')

        from apps.permissions.models import RolePermission
        admin_perm = RolePermission.objects.get(role='admin', module_name='finance')
        self.assertEqual(admin_perm.access_level, 'full_access')
        sales_perm = RolePermission.objects.get(role='sales', module_name='finance')
        self.assertEqual(sales_perm.access_level, 'no_access')

    def test_running_twice_does_not_duplicate_accounts(self):
        migration = importlib.import_module(
            'apps.finance.migrations.0002_default_accounts_and_permissions'
        )
        from django.apps import apps as global_apps
        migration.create_default_accounts(global_apps, None)
        migration.create_default_accounts(global_apps, None)
        self.assertEqual(FinancialAccount.objects.count(), 4)


class AccountCreationTests(TestCase):
    """#2: A new account can be added."""

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.client_http = HttpClient()
        self.client_http.force_login(self.admin)

    def test_account_created_via_view(self):
        response = self.client_http.post('/finance/accounts/add/', {
            'name': 'New Test Bank', 'code': 'NEW-BANK', 'account_type': 'bank',
            'currency': 'KES', 'opening_balance': '1000.00', 'opening_balance_date': '2026-01-01',
            'status': 'active',
        })
        self.assertEqual(response.status_code, 302)
        account = FinancialAccount.objects.get(code='NEW-BANK')
        self.assertEqual(account.name, 'New Test Bank')
        self.assertEqual(account.opening_balance, Decimal('1000.00'))
        self.assertEqual(account.created_by, self.admin)


class AccountLedgerViewTests(TestCase):
    """#3: Account ledger opens correctly."""

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account()
        self.client_http = HttpClient()
        self.client_http.force_login(self.admin)

    def test_ledger_page_loads_for_empty_account(self):
        response = self.client_http.get(f'/finance/accounts/{self.account.pk}/ledger/')
        self.assertEqual(response.status_code, 200)

    def test_ledger_page_loads_with_transactions(self):
        services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('500'), created_by=self.admin,
        )
        response = self.client_http.get(f'/finance/accounts/{self.account.pk}/ledger/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TXN-')


class AccountBalanceCalculationTests(TestCase):
    """#16: Account balances match ledger calculations.

    Current Approved Balance = Opening Balance + Approved Credits - Approved Debits
    Available Balance = Current Approved Balance + Pending Inflows - Pending Outflows
    """

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(opening_balance=Decimal('1000.00'), require_approval=True)

    def test_balance_formula(self):
        credit_pending = services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('300'), created_by=self.admin,
        )
        debit_pending = services.create_transaction(
            self.account, direction='debit', transaction_type='bank_withdrawal',
            amount=Decimal('100'), created_by=self.admin,
        )
        # Nothing approved yet: current balance == opening balance.
        self.assertEqual(self.account.current_balance, Decimal('1000.00'))
        self.assertEqual(self.account.pending_inflows, Decimal('300'))
        self.assertEqual(self.account.pending_outflows, Decimal('100'))
        self.assertEqual(self.account.available_balance, Decimal('1200.00'))

        approver = make_user('approver@test.com', is_superuser=True)
        services.approve_transaction(credit_pending, approver)
        services.approve_transaction(debit_pending, approver)

        self.assertEqual(self.account.current_balance, Decimal('1200.00'))
        self.assertEqual(self.account.pending_inflows, Decimal('0.00'))
        self.assertEqual(self.account.available_balance, Decimal('1200.00'))

    def test_account_without_require_approval_auto_approves(self):
        account = make_account(code='NO-APPROVAL', require_approval=False, opening_balance=Decimal('0'))
        services.create_transaction(
            account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('250'), created_by=self.admin,
        )
        self.assertEqual(account.current_balance, Decimal('250'))
        self.assertEqual(account.pending_inflows, Decimal('0'))
