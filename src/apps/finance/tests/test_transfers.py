"""
Covers spec Testing Requirement #6: internal transfer creates debit and
credit linked entries.
"""
from decimal import Decimal

from django.test import TestCase

from apps.finance import services

from .factories import make_account, make_user


class InternalTransferTests(TestCase):

    def setUp(self):
        self.user = make_user('transfer_user@test.com', is_superuser=True)
        self.from_account = make_account(code='FROM-ACC', opening_balance=Decimal('10000'), require_approval=False)
        self.to_account = make_account(code='TO-ACC', opening_balance=Decimal('0'), require_approval=False)

    def test_transfer_creates_linked_debit_and_credit(self):
        transfer = services.create_internal_transfer(
            from_account=self.from_account, to_account=self.to_account,
            amount=Decimal('3000'), created_by=self.user,
        )

        self.assertEqual(transfer.debit_transaction.direction, 'debit')
        self.assertEqual(transfer.debit_transaction.account_id, self.from_account.pk)
        self.assertEqual(transfer.credit_transaction.direction, 'credit')
        self.assertEqual(transfer.credit_transaction.account_id, self.to_account.pk)
        self.assertEqual(transfer.debit_transaction.amount, Decimal('3000'))
        self.assertEqual(transfer.credit_transaction.amount, Decimal('3000'))

        # Both legs share the same transfer reference trail via the transfer object.
        self.assertEqual(transfer.debit_transaction.transaction_type, 'internal_transfer_sent')
        self.assertEqual(transfer.credit_transaction.transaction_type, 'internal_transfer_received')

        self.assertEqual(self.from_account.current_balance, Decimal('7000'))
        self.assertEqual(self.to_account.current_balance, Decimal('3000'))

    def test_transfer_requiring_approval_holds_both_legs_pending_until_approved(self):
        from_account = make_account(code='FROM-APPROVE', opening_balance=Decimal('10000'), require_approval=True)
        to_account = make_account(code='TO-APPROVE', opening_balance=Decimal('0'), require_approval=False)

        transfer = services.create_internal_transfer(
            from_account=from_account, to_account=to_account,
            amount=Decimal('2000'), created_by=self.user,
        )
        self.assertEqual(transfer.status, 'pending_approval')
        self.assertEqual(transfer.debit_transaction.status, 'pending_approval')
        self.assertEqual(transfer.credit_transaction.status, 'pending_approval')
        self.assertEqual(from_account.current_balance, Decimal('10000'))
        self.assertEqual(to_account.current_balance, Decimal('0'))

        services.approve_internal_transfer(transfer, self.user)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'approved')
        self.assertEqual(from_account.current_balance, Decimal('8000'))
        self.assertEqual(to_account.current_balance, Decimal('2000'))

    def test_cannot_transfer_account_to_itself(self):
        with self.assertRaises(ValueError):
            services.create_internal_transfer(
                from_account=self.from_account, to_account=self.from_account,
                amount=Decimal('100'), created_by=self.user,
            )

    def test_rejecting_a_transfer_rejects_both_legs(self):
        from_account = make_account(code='FROM-REJECT', opening_balance=Decimal('5000'), require_approval=True)
        to_account = make_account(code='TO-REJECT', opening_balance=Decimal('0'), require_approval=True)

        transfer = services.create_internal_transfer(
            from_account=from_account, to_account=to_account,
            amount=Decimal('1000'), created_by=self.user,
        )
        services.reject_internal_transfer(transfer, self.user, comments='Wrong destination')

        transfer.refresh_from_db()
        transfer.debit_transaction.refresh_from_db()
        transfer.credit_transaction.refresh_from_db()
        self.assertEqual(transfer.status, 'rejected')
        self.assertEqual(transfer.debit_transaction.status, 'rejected')
        self.assertEqual(transfer.credit_transaction.status, 'rejected')
        self.assertEqual(from_account.current_balance, Decimal('5000'))
        self.assertEqual(to_account.current_balance, Decimal('0'))
