"""
Admin configuration for the finance app.
"""
from django.contrib import admin

from .models import (
    FinancialAccount, LedgerTransaction, TransactionApproval,
    TransactionAuditTrail, InternalTransfer, AccountReconciliation,
    SuspenseTransaction, PaymentAllocation,
)


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'account_type', 'currency', 'opening_balance',
        'current_balance', 'status', 'is_default', 'require_approval',
    )
    list_filter = ('account_type', 'status', 'is_default', 'require_approval')
    search_fields = ('name', 'code', 'bank_name', 'account_number', 'paybill_number', 'till_number')
    readonly_fields = ('created_at', 'updated_at')

    def current_balance(self, obj):
        return obj.current_balance
    current_balance.short_description = 'Current Balance'


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'account', 'transaction_date', 'direction',
        'transaction_type', 'amount', 'status', 'source_module', 'created_by',
    )
    list_filter = ('direction', 'transaction_type', 'status', 'source_module', 'account')
    search_fields = (
        'reference_number', 'description', 'related_party_label',
        'related_client__first_name', 'related_client__last_name',
        'related_vehicle__registration_number', 'related_vehicle__vin',
    )
    readonly_fields = ('reference_number', 'created_at', 'updated_at')
    autocomplete_fields = ()
    date_hierarchy = 'transaction_date'


@admin.register(TransactionApproval)
class TransactionApprovalAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'action', 'actioned_by', 'actioned_at')
    list_filter = ('action',)


@admin.register(TransactionAuditTrail)
class TransactionAuditTrailAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'action', 'changed_by', 'changed_at')
    list_filter = ('action',)


@admin.register(InternalTransfer)
class InternalTransferAdmin(admin.ModelAdmin):
    list_display = (
        'transfer_reference', 'from_account', 'to_account', 'amount',
        'transfer_date', 'status', 'created_by',
    )
    list_filter = ('status',)
    readonly_fields = ('transfer_reference', 'created_at')


@admin.register(AccountReconciliation)
class AccountReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        'account', 'reconciliation_date', 'statement_balance',
        'book_balance', 'difference', 'status', 'reconciled_by',
    )
    list_filter = ('status', 'account')
    readonly_fields = ('difference', 'created_at')


@admin.register(SuspenseTransaction)
class SuspenseTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'is_allocated', 'allocated_by', 'allocated_at')
    list_filter = ('is_allocated',)


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'payment_schedule', 'amount_allocated', 'created_at')
