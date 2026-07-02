"""
Covers spec Testing Requirement #13: reports filter correctly.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.finance import services
from apps.finance.reports import filter_transactions, period_summary, summarize

from .factories import make_account, make_finance_permission, make_user
from utils.constants import AccessLevel, UserRole


class ReportFilteringTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account_a = make_account(code='ACC-A', require_approval=False)
        self.account_b = make_account(code='ACC-B', require_approval=False)

        self.expense_txn = services.create_transaction(
            self.account_a, direction='debit', transaction_type='staff_expense',
            amount=Decimal('1000'), created_by=self.admin, source_module='expenses',
        )
        self.payment_txn = services.create_transaction(
            self.account_a, direction='credit', transaction_type='client_vehicle_payment',
            amount=Decimal('5000'), created_by=self.admin, source_module='payments',
        )
        self.vendor_txn = services.create_transaction(
            self.account_b, direction='debit', transaction_type='broker_commission',
            amount=Decimal('2000'), created_by=self.admin, source_module='vehicles',
        )

    def test_filter_by_report_type_client_payments(self):
        qs = filter_transactions('client_payments')
        self.assertEqual(list(qs), [self.payment_txn])

    def test_filter_by_report_type_expenses(self):
        qs = filter_transactions('expenses')
        self.assertEqual(list(qs), [self.expense_txn])

    def test_filter_by_report_type_vendor_payments(self):
        qs = filter_transactions('vendor_payments')
        self.assertEqual(list(qs), [self.vendor_txn])

    def test_filter_by_account(self):
        qs = filter_transactions('all', account=self.account_b)
        self.assertEqual(list(qs), [self.vendor_txn])

    def test_filter_by_status_pending(self):
        pending_account = make_account(code='PENDING', require_approval=True)
        pending_txn = services.create_transaction(
            pending_account, direction='credit', transaction_type='cash_deposit',
            amount=Decimal('100'), created_by=self.admin,
        )
        qs = filter_transactions('pending')
        self.assertEqual(list(qs), [pending_txn])

    def test_summarize_totals_only_count_approved_and_reversed(self):
        summary = summarize(filter_transactions('all', account=self.account_a))
        self.assertEqual(summary['count'], 2)
        self.assertEqual(summary['total_credits'], Decimal('5000'))
        self.assertEqual(summary['total_debits'], Decimal('1000'))
        self.assertEqual(summary['net'], Decimal('4000'))

    def test_period_summary_groups_by_month(self):
        rows = period_summary('monthly', account=self.account_a)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['credits'], Decimal('5000'))
        self.assertEqual(rows[0]['debits'], Decimal('1000'))
        self.assertEqual(rows[0]['net'], Decimal('4000'))


class ReportViewAndExportTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(require_approval=False)
        self.txn = services.create_transaction(
            self.account, direction='credit', transaction_type='client_vehicle_payment',
            amount=Decimal('7500'), created_by=self.admin, source_module='payments',
        )
        self.http = HttpClient()
        self.http.force_login(self.admin)

    def test_reports_page_filters_via_query_params(self):
        response = self.http.get('/finance/reports/', {'report_type': 'client_payments'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.txn.reference_number)

    def test_csv_export_contains_expected_row(self):
        response = self.http.get('/finance/reports/export/csv/', {'report_type': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode()
        self.assertIn(self.txn.reference_number, content)
        self.assertIn('7500.00', content)

    def test_export_blocked_without_can_export_permission(self):
        make_finance_permission(UserRole.CLERK, access_level=AccessLevel.READ_ONLY,
                                 can_create=False, can_edit=False, can_delete=False, can_export=False)
        clerk = make_user('clerk_export@test.com', role=UserRole.CLERK)
        http = HttpClient()
        http.force_login(clerk)
        response = http.get('/finance/reports/export/csv/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
