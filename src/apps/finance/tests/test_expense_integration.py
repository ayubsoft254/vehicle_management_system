"""
Covers spec Testing Requirement #5: expense creates a debit transaction.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase

from apps.expenses.models import Expense
from apps.finance.models import LedgerTransaction

from .factories import make_account, make_expense_category, make_user


class ExpenseCreatesLedgerDebitTests(TestCase):

    def setUp(self):
        self.admin = make_user('admin@test.com', is_superuser=True)
        self.account = make_account(require_approval=False)
        self.category = make_expense_category()
        self.http = HttpClient()
        self.http.force_login(self.admin)

    def _create_expense(self, amount='15000'):
        response = self.http.post('/expenses/create/', {
            'title': 'Office rent', 'description': 'Monthly rent', 'category': self.category.pk,
            'amount': amount, 'currency': 'KES', 'tax_amount': '0', 'expense_date': '2026-01-05',
            'payment_method': 'BANK_TRANSFER', 'vendor_name': 'Landlord Co', 'account': self.account.pk,
        })
        self.assertEqual(response.status_code, 302, response.content[:500] if response.status_code != 302 else '')
        return Expense.objects.latest('created_at')

    def test_no_ledger_transaction_until_marked_paid(self):
        expense = self._create_expense()
        self.assertEqual(expense.status, 'DRAFT')
        self.assertFalse(LedgerTransaction.objects.filter(source_module='expenses').exists())

    def test_marking_paid_creates_a_debit_transaction(self):
        expense = self._create_expense(amount='15000')
        expense.status = 'APPROVED'
        expense.approved_by = self.admin
        expense.save()

        response = self.http.post(f'/expenses/{expense.pk}/mark-paid/')
        self.assertEqual(response.status_code, 200)

        expense.refresh_from_db()
        self.assertEqual(expense.status, 'PAID')

        txn = LedgerTransaction.objects.get(source_module='expenses')
        self.assertEqual(txn.direction, 'debit')
        self.assertEqual(txn.amount, expense.total_amount)
        self.assertEqual(txn.account_id, self.account.pk)
        self.assertEqual(txn.status, 'approved')  # account doesn't require approval

    def test_cannot_mark_paid_before_approval(self):
        expense = self._create_expense()
        response = self.http.post(f'/expenses/{expense.pk}/mark-paid/')
        self.assertEqual(response.status_code, 400)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'DRAFT')
        self.assertFalse(LedgerTransaction.objects.filter(source_module='expenses').exists())

    def test_expense_without_account_does_not_create_ledger_transaction(self):
        # Simulates a pre-finance-module expense (account left blank).
        expense = self._create_expense()
        expense.account = None
        expense.status = 'APPROVED'
        expense.approved_by = self.admin
        expense.save()

        response = self.http.post(f'/expenses/{expense.pk}/mark-paid/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LedgerTransaction.objects.filter(source_module='expenses').exists())
