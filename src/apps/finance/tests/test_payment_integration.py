"""
Covers spec Testing Requirements #4 (client payment creates a credit
transaction) and #12 (payment allocation updates vehicle balance and
instalments).
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.finance.models import LedgerTransaction, PaymentAllocation
from apps.payments.models import PaymentSchedule

from .factories import make_account, make_client_vehicle, make_user


class ClientPaymentCreatesLedgerCreditTests(TestCase):
    """#4."""

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(require_approval=True)
        self.cv = make_client_vehicle(with_installment_plan=True)
        self.http = HttpClient()
        self.http.force_login(self.admin)

    def test_recording_a_payment_creates_a_credit_ledger_transaction(self):
        response = self.http.post(f'/payments/record/{self.cv.pk}/', {
            'amount': '30000.00', 'payment_date': '2026-01-05', 'payment_method': 'bank_transfer',
            'payment_location': 'Head Office', 'transaction_reference': 'REF001',
            'account': self.account.pk, 'notes': '',
        })
        self.assertEqual(response.status_code, 302)

        txn = LedgerTransaction.objects.filter(source_module='payments').latest('created_at')
        self.assertEqual(txn.direction, 'credit')
        self.assertEqual(txn.amount, Decimal('30000.00'))
        self.assertEqual(txn.transaction_type, 'hire_purchase_instalment')
        self.assertEqual(txn.account_id, self.account.pk)
        self.assertEqual(txn.related_client_id, self.cv.client_id)
        self.assertEqual(txn.related_vehicle_id, self.cv.vehicle_id)

    def test_payment_without_installment_plan_uses_client_vehicle_payment_type(self):
        cv_no_plan = make_client_vehicle(
            with_installment_plan=False,
            client_id_number='TESTID002', vehicle_vin='TESTVIN0000000002',
        )
        response = self.http.post(f'/payments/record/{cv_no_plan.pk}/', {
            'amount': '50000.00', 'payment_date': '2026-01-05', 'payment_method': 'cash',
            'account': self.account.pk,
        })
        self.assertEqual(response.status_code, 302)
        txn = LedgerTransaction.objects.filter(source_module='payments').latest('created_at')
        self.assertEqual(txn.transaction_type, 'client_vehicle_payment')


class PaymentAllocationTests(TestCase):
    """#12: paying more than one instalment at once allocates across
    multiple PaymentSchedule rows and updates the vehicle balance/progress."""

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(require_approval=True)
        # KES 30,000/month, 40 months -> paying 120,000 should settle 4 instalments.
        self.cv = make_client_vehicle(
            with_installment_plan=True, monthly_installment=Decimal('30000'), number_of_installments=40,
        )
        self.http = HttpClient()
        self.http.force_login(self.admin)

    def test_bulk_payment_settles_multiple_instalments_and_updates_balance(self):
        response = self.http.post(f'/payments/record/{self.cv.pk}/', {
            'amount': '120000.00', 'payment_date': '2026-01-05', 'payment_method': 'bank_transfer',
            'transaction_reference': 'REF-BULK', 'account': self.account.pk,
        })
        self.assertEqual(response.status_code, 302)

        self.cv.refresh_from_db()
        self.assertEqual(self.cv.total_paid, Decimal('120000.00'))
        self.assertEqual(self.cv.balance, Decimal('1080000.00'))

        paid_schedules = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle=self.cv, is_paid=True
        )
        self.assertEqual(paid_schedules.count(), 4)

        txn = LedgerTransaction.objects.filter(source_module='payments').latest('created_at')
        allocations = PaymentAllocation.objects.filter(transaction=txn)
        self.assertEqual(allocations.count(), 4)
        self.assertEqual(
            sum((a.amount_allocated for a in allocations), Decimal('0.00')),
            Decimal('120000.00'),
        )

    def test_partial_instalment_payment_does_not_mark_schedule_paid(self):
        response = self.http.post(f'/payments/record/{self.cv.pk}/', {
            'amount': '10000.00', 'payment_date': '2026-01-05', 'payment_method': 'cash',
            'account': self.account.pk,
        })
        self.assertEqual(response.status_code, 302)

        self.cv.refresh_from_db()
        self.assertEqual(self.cv.total_paid, Decimal('10000.00'))
        paid_schedules = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle=self.cv, is_paid=True
        )
        self.assertEqual(paid_schedules.count(), 0)
