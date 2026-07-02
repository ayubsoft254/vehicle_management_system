"""
Coverage for reconciliation and suspense allocation (Phase 6), beyond the
spec's core 16 testing requirements.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.finance import services
from apps.finance.models import AccountReconciliation, SuspenseTransaction

from .factories import make_account, make_client, make_user


class ReconciliationTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(opening_balance=Decimal('1000'), require_approval=False)
        self.http = HttpClient()
        self.http.force_login(self.admin)

    def test_starting_a_reconciliation_captures_book_balance_and_computes_difference(self):
        services.create_transaction(
            self.account, direction='credit', transaction_type='bank_deposit',
            amount=Decimal('500'), created_by=self.admin,
        )
        response = self.http.post(f'/finance/accounts/{self.account.pk}/reconciliations/add/', {
            'reconciliation_date': '2026-01-10', 'statement_balance': '1400.00', 'notes': 'test',
        })
        self.assertEqual(response.status_code, 302)

        recon = AccountReconciliation.objects.latest('id')
        self.assertEqual(recon.book_balance, Decimal('1500.00'))
        self.assertEqual(recon.statement_balance, Decimal('1400.00'))
        self.assertEqual(recon.difference, Decimal('-100.00'))
        self.assertEqual(recon.status, 'in_progress')

    def test_completing_a_reconciliation_records_who_and_when(self):
        recon = AccountReconciliation.objects.create(
            account=self.account, reconciliation_date='2026-01-10',
            statement_balance=Decimal('1000'), book_balance=Decimal('1000'),
        )
        services.complete_reconciliation(recon, self.admin)
        recon.refresh_from_db()
        self.assertEqual(recon.status, 'completed')
        self.assertEqual(recon.reconciled_by, self.admin)
        self.assertIsNotNone(recon.reconciled_at)

    def test_cannot_complete_an_already_completed_reconciliation(self):
        recon = AccountReconciliation.objects.create(
            account=self.account, reconciliation_date='2026-01-10',
            statement_balance=Decimal('1000'), book_balance=Decimal('1000'),
            status='completed', reconciled_by=self.admin,
        )
        with self.assertRaises(ValueError):
            services.complete_reconciliation(recon, self.admin)


class SuspenseAllocationTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.suspense_account = make_account(code='SUSPENSE', account_type='suspense', require_approval=True)

    def test_credit_to_suspense_account_auto_creates_suspense_transaction(self):
        txn = services.create_transaction(
            self.suspense_account, direction='credit', transaction_type='suspense_allocation',
            amount=Decimal('4000'), created_by=self.admin,
        )
        suspense_row = SuspenseTransaction.objects.get(transaction=txn)
        self.assertFalse(suspense_row.is_allocated)

    def test_debit_from_suspense_account_does_not_create_suspense_transaction(self):
        services.create_transaction(
            self.suspense_account, direction='debit', transaction_type='bank_withdrawal',
            amount=Decimal('1000'), created_by=self.admin,
        )
        self.assertEqual(SuspenseTransaction.objects.count(), 0)

    def test_allocating_a_suspense_payment_tags_the_transaction_and_marks_resolved(self):
        txn = services.create_transaction(
            self.suspense_account, direction='credit', transaction_type='suspense_allocation',
            amount=Decimal('4000'), created_by=self.admin,
        )
        suspense_row = SuspenseTransaction.objects.get(transaction=txn)
        client = make_client()

        services.allocate_suspense_transaction(suspense_row, self.admin, client=client, notes='Identified via callback')

        suspense_row.refresh_from_db()
        txn.refresh_from_db()
        self.assertTrue(suspense_row.is_allocated)
        self.assertEqual(suspense_row.allocated_by, self.admin)
        self.assertEqual(txn.related_client, client)

    def test_cannot_reallocate_an_already_allocated_payment(self):
        txn = services.create_transaction(
            self.suspense_account, direction='credit', transaction_type='suspense_allocation',
            amount=Decimal('4000'), created_by=self.admin,
        )
        suspense_row = SuspenseTransaction.objects.get(transaction=txn)
        client = make_client()
        services.allocate_suspense_transaction(suspense_row, self.admin, client=client)

        with self.assertRaises(ValueError):
            services.allocate_suspense_transaction(suspense_row, self.admin, client=client)

    def test_allocation_requires_a_client_or_vehicle(self):
        txn = services.create_transaction(
            self.suspense_account, direction='credit', transaction_type='suspense_allocation',
            amount=Decimal('4000'), created_by=self.admin,
        )
        suspense_row = SuspenseTransaction.objects.get(transaction=txn)
        with self.assertRaises(ValueError):
            services.allocate_suspense_transaction(suspense_row, self.admin)
