"""
Covers spec Testing Requirements #7 (pending doesn't affect approved balance),
#8 (approved transactions affect balance correctly), #9 (rejected transactions
don't affect balance).
"""
from decimal import Decimal

from django.test import TestCase

from apps.finance import services

from .factories import make_account, make_user


class PendingApprovedRejectedBalanceTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(opening_balance=Decimal('0.00'), require_approval=True)

    def test_pending_transaction_does_not_affect_approved_balance(self):
        services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('5000'), created_by=self.admin,
        )
        self.assertEqual(self.account.current_balance, Decimal('0.00'))
        self.assertEqual(self.account.pending_inflows, Decimal('5000'))

    def test_approved_transaction_affects_balance_correctly(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('5000'), created_by=self.admin,
        )
        approver = make_user('approver@test.com', is_superuser=True)
        services.approve_transaction(txn, approver)

        self.assertEqual(txn.status, 'approved')
        self.assertEqual(self.account.current_balance, Decimal('5000'))
        self.assertEqual(self.account.pending_inflows, Decimal('0'))

    def test_rejected_transaction_does_not_affect_balance(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('5000'), created_by=self.admin,
        )
        approver = make_user('approver@test.com', is_superuser=True)
        services.reject_transaction(txn, approver, comments='Duplicate entry')

        self.assertEqual(txn.status, 'rejected')
        self.assertEqual(self.account.current_balance, Decimal('0.00'))
        self.assertEqual(self.account.pending_inflows, Decimal('0.00'))
        self.assertEqual(self.account.available_balance, Decimal('0.00'))

    def test_cannot_approve_a_rejected_transaction(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('5000'), created_by=self.admin,
        )
        approver = make_user('approver@test.com', is_superuser=True)
        services.reject_transaction(txn, approver)
        with self.assertRaises(ValueError):
            services.approve_transaction(txn, approver)

    def test_missing_amount_or_account_is_rejected(self):
        with self.assertRaises(Exception):
            services.create_transaction(
                None, direction='credit', transaction_type='cash_deposit',
                amount=Decimal('100'), created_by=self.admin,
            )
