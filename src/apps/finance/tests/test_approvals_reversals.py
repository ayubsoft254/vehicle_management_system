"""
Covers spec Testing Requirements #10 (reversal creates a proper reversing
entry), #11 (corrected transactions preserve audit trail), #15 (user cannot
approve own transaction unless allowed).
"""
from decimal import Decimal

from django.test import TestCase

from apps.finance import services
from apps.finance.models import LedgerTransaction, TransactionAuditTrail

from .factories import make_account, make_user


class SelfApprovalRestrictionTests(TestCase):
    """#15."""

    def setUp(self):
        self.account = make_account(opening_balance=Decimal('0.00'), require_approval=True)

    def test_creator_cannot_approve_own_transaction(self):
        creator = make_user('creator@test.com', is_superuser=False)
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('1000'), created_by=creator,
        )
        with self.assertRaises(PermissionError):
            services.approve_transaction(txn, creator)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'pending_approval')

    def test_superuser_can_approve_own_transaction(self):
        superuser = make_user('super@test.com', is_superuser=True)
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('1000'), created_by=superuser,
        )
        services.approve_transaction(txn, superuser)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'approved')

    def test_different_user_can_approve(self):
        creator = make_user('creator2@test.com')
        approver = make_user('approver2@test.com', is_superuser=True)
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('1000'), created_by=creator,
        )
        services.approve_transaction(txn, approver)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'approved')
        self.assertEqual(txn.approved_by, approver)


class ReversalTests(TestCase):
    """#10."""

    def setUp(self):
        self.account = make_account(opening_balance=Decimal('0.00'), require_approval=False)
        self.user = make_user('user@test.com', is_superuser=True)

    def _approved_credit(self, amount):
        return services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=amount, created_by=self.user,
        )

    def test_reversal_creates_opposite_direction_linked_entry(self):
        original = self._approved_credit(Decimal('10000'))
        self.assertEqual(self.account.current_balance, Decimal('10000'))

        reversal = services.reverse_transaction(original, self.user, 'Wrong account credited')

        original.refresh_from_db()
        self.assertEqual(original.status, 'reversed')
        self.assertEqual(reversal.direction, 'debit')
        self.assertEqual(reversal.amount, original.amount)
        self.assertTrue(reversal.is_reversal)
        self.assertEqual(reversal.original_transaction_id, original.pk)
        self.assertEqual(reversal.status, 'approved')
        # Net effect: reversal fully offsets the original, never hides it.
        self.assertEqual(self.account.current_balance, Decimal('0.00'))

    def test_only_approved_transactions_can_be_reversed(self):
        pending_account = make_account(code='PENDING-ACC', require_approval=True)
        pending_txn = services.create_transaction(
            pending_account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('500'), created_by=self.user,
        )
        with self.assertRaises(ValueError):
            services.reverse_transaction(pending_txn, self.user, 'test')

    def test_a_reversal_entry_cannot_itself_be_reversed(self):
        original = self._approved_credit(Decimal('1000'))
        reversal = services.reverse_transaction(original, self.user, 'reason')
        with self.assertRaises(ValueError):
            services.reverse_transaction(reversal, self.user, 'reason again')

    def test_reversal_requires_a_reason(self):
        original = self._approved_credit(Decimal('1000'))
        with self.assertRaises(ValueError):
            services.reverse_transaction(original, self.user, '')


class CorrectionTests(TestCase):
    """#11: corrected transactions preserve audit trail (original is kept,
    linked, and the full trail — old and new — remains visible)."""

    def setUp(self):
        self.account = make_account(opening_balance=Decimal('0.00'), require_approval=False)
        self.user = make_user('corrector@test.com', is_superuser=True)

    def test_correction_reverses_and_reposts_correct_amount(self):
        # Spec's worked example: KES 300,000 recorded by mistake instead of 30,000.
        original = services.create_transaction(
            self.account, direction='debit', transaction_type='cash_withdrawal',
            amount=Decimal('300000'), created_by=self.user,
        )
        self.assertEqual(self.account.current_balance, Decimal('-300000'))

        reversal, corrected = services.correct_transaction(
            original, self.user, Decimal('30000'), 'Typo: entered 300000 instead of 30000'
        )

        original.refresh_from_db()
        self.assertEqual(original.status, 'reversed')
        self.assertEqual(original.amount, Decimal('300000'), 'Original record must never be altered')

        self.assertTrue(reversal.is_reversal)
        self.assertEqual(reversal.original_transaction_id, original.pk)

        self.assertTrue(corrected.is_correction)
        self.assertEqual(corrected.original_transaction_id, original.pk)
        self.assertEqual(corrected.amount, Decimal('30000'))
        self.assertEqual(corrected.correction_reason, 'Typo: entered 300000 instead of 30000')

        self.assertEqual(self.account.current_balance, Decimal('-30000'))

        # The original transaction is still visible and traceable, not deleted.
        self.assertTrue(LedgerTransaction.objects.filter(pk=original.pk).exists())
        self.assertIn(reversal, original.related_entries.all())
        self.assertIn(corrected, original.related_entries.all())

    def test_correction_requires_a_reason(self):
        original = services.create_transaction(
            self.account, direction='debit', transaction_type='cash_withdrawal',
            amount=Decimal('1000'), created_by=self.user,
        )
        with self.assertRaises(ValueError):
            services.correct_transaction(original, self.user, Decimal('900'), '')

    def test_audit_trail_records_create_reverse_and_correct_actions(self):
        original = services.create_transaction(
            self.account, direction='debit', transaction_type='cash_withdrawal',
            amount=Decimal('300000'), created_by=self.user,
        )
        services.correct_transaction(original, self.user, Decimal('30000'), 'Typo fix')

        actions = list(
            TransactionAuditTrail.objects.filter(transaction=original).values_list('action', flat=True)
        )
        self.assertIn('create', actions)
        self.assertIn('reverse', actions)
        self.assertIn('correct', actions)


class EditBeforeApprovalTests(TestCase):
    """Spec section 8: mistakes before approval can be edited directly, with
    a required reason and preserved edit history — as opposed to approved
    transactions, which must go through reverse_transaction()/correct_transaction()."""

    def setUp(self):
        self.account = make_account(require_approval=True)
        self.user = make_user('editor@test.com', is_superuser=True)

    def test_pending_transaction_can_be_edited_with_reason(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('1000'), created_by=self.user, description='original',
        )
        services.edit_transaction(txn, self.user, 'Fixing amount', amount=Decimal('1500'), description='corrected')
        txn.refresh_from_db()
        self.assertEqual(txn.amount, Decimal('1500'))
        self.assertEqual(txn.description, 'corrected')
        self.assertEqual(txn.edit_reason, 'Fixing amount')
        self.assertEqual(txn.status, 'pending_approval')

    def test_edit_requires_a_reason(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('1000'), created_by=self.user,
        )
        with self.assertRaises(ValueError):
            services.edit_transaction(txn, self.user, '', amount=Decimal('1200'))

    def test_approved_transaction_cannot_be_edited(self):
        txn = services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('1000'), created_by=self.user,
        )
        services.approve_transaction(txn, make_user('other_approver@test.com', is_superuser=True))
        with self.assertRaises(ValueError):
            services.edit_transaction(txn, self.user, 'trying anyway', amount=Decimal('2000'))
