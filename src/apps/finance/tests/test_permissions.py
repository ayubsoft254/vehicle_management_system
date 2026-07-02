"""
Covers spec Testing Requirement #14: permission restrictions work correctly.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.finance import services
from utils.constants import AccessLevel, UserRole

from .factories import make_account, make_finance_permission, make_user


class ModuleAccessRestrictionTests(TestCase):

    def test_no_access_role_is_blocked_from_finance_module(self):
        make_finance_permission(UserRole.SALES, access_level=AccessLevel.NO_ACCESS,
                                 can_create=False, can_edit=False, can_delete=False, can_export=False)
        user = make_user('sales@test.com', role=UserRole.SALES)
        http = HttpClient()
        http.force_login(user)

        response = http.get('/finance/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], '/dashboard/')

    def test_read_only_role_can_view_but_not_add_account(self):
        make_finance_permission(UserRole.CLERK, access_level=AccessLevel.READ_ONLY,
                                 can_create=False, can_edit=False, can_delete=False, can_export=False)
        clerk = make_user('clerk@test.com', role=UserRole.CLERK)
        http = HttpClient()
        http.force_login(clerk)

        response = http.get('/finance/')
        self.assertEqual(response.status_code, 200)

        response = http.get('/finance/accounts/add/', follow=True)
        self.assertEqual(response.redirect_chain[-1][0], '/finance/accounts/')

    def test_role_with_can_create_can_record_transaction_but_not_approve(self):
        make_finance_permission(UserRole.CLERK, access_level=AccessLevel.READ_WRITE,
                                 can_create=True, can_edit=False, can_delete=False, can_export=False)
        cashier = make_user('cashier@test.com', role=UserRole.CLERK)
        account = make_account(require_approval=True)
        http = HttpClient()
        http.force_login(cashier)

        response = http.post(f'/finance/accounts/{account.pk}/transactions/add/', {
            'transaction_date': '2026-01-05', 'direction': 'credit', 'transaction_type': 'cash_deposit',
            'amount': '500', 'currency': 'KES', 'payment_method': 'cash', 'description': 'test',
        })
        self.assertEqual(response.status_code, 302)

        from apps.finance.models import LedgerTransaction
        txn = LedgerTransaction.objects.latest('created_at')

        response = http.post(f'/finance/transactions/{txn.pk}/approve/', follow=True)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'pending_approval', 'Cashier must not be able to approve')

    def test_role_with_can_edit_can_approve(self):
        make_finance_permission(UserRole.ACCOUNTANT, access_level=AccessLevel.FULL_ACCESS,
                                 can_create=True, can_edit=True, can_delete=False, can_export=True)
        accountant = make_user('accountant@test.com', role=UserRole.ACCOUNTANT)
        cashier_created_by = make_user('other_cashier@test.com', role=UserRole.CLERK)
        account = make_account(require_approval=True)
        txn = services.create_transaction(
            account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('500'), created_by=cashier_created_by,
        )
        http = HttpClient()
        http.force_login(accountant)

        response = http.post(f'/finance/transactions/{txn.pk}/approve/')
        self.assertEqual(response.status_code, 302)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'approved')

    def test_reversal_restricted_to_can_delete_permission(self):
        make_finance_permission(UserRole.ACCOUNTANT, access_level=AccessLevel.FULL_ACCESS,
                                 can_create=True, can_edit=True, can_delete=False, can_export=True)
        accountant = make_user('accountant2@test.com', role=UserRole.ACCOUNTANT)
        account = make_account(require_approval=False)
        txn = services.create_transaction(
            account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('500'), created_by=make_user('creator@test.com', is_superuser=True),
        )
        http = HttpClient()
        http.force_login(accountant)

        response = http.post(f'/finance/transactions/{txn.pk}/reverse/', {'reason': 'test'}, follow=True)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'approved', 'Accountant without can_delete must not be able to reverse')

        make_finance_permission(UserRole.ACCOUNTANT, access_level=AccessLevel.FULL_ACCESS,
                                 can_create=True, can_edit=True, can_delete=True, can_export=True)
        response = http.post(f'/finance/transactions/{txn.pk}/reverse/', {'reason': 'test'})
        self.assertEqual(response.status_code, 302)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'reversed')

    def test_superuser_bypasses_all_permission_checks(self):
        superuser = make_user('super@test.com', is_superuser=True)
        http = HttpClient()
        http.force_login(superuser)
        response = http.get('/finance/')
        self.assertEqual(response.status_code, 200)
        response = http.get('/finance/accounts/add/')
        self.assertEqual(response.status_code, 200)
