"""
URL configuration for the finance app.
"""
from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.finance_dashboard, name='finance_dashboard'),

    # Account management
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/add/', views.account_add, name='account_add'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<int:pk>/toggle-status/', views.account_toggle_status, name='account_toggle_status'),
    path('accounts/<int:pk>/ledger/', views.account_ledger, name='account_ledger'),
    path('accounts/<int:pk>/transactions/add/', views.transaction_add, name='transaction_add'),

    # Transactions
    path('transactions/pending/', views.pending_approvals, name='pending_approvals'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<int:pk>/approve/', views.transaction_approve, name='transaction_approve'),
    path('transactions/<int:pk>/reject/', views.transaction_reject, name='transaction_reject'),
    path('transactions/<int:pk>/request-edit/', views.transaction_request_edit, name='transaction_request_edit'),
    path('transactions/<int:pk>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<int:pk>/reverse/', views.transaction_reverse, name='transaction_reverse'),
    path('transactions/<int:pk>/correct/', views.transaction_correct, name='transaction_correct'),

    # Internal transfers
    path('transfers/add/', views.transfer_add, name='transfer_add'),
    path('transfers/<int:pk>/', views.transfer_detail, name='transfer_detail'),
    path('transfers/<int:pk>/approve/', views.transfer_approve, name='transfer_approve'),
    path('transfers/<int:pk>/reject/', views.transfer_reject, name='transfer_reject'),

    # Reconciliation
    path('accounts/<int:pk>/reconciliations/', views.account_reconciliation_list, name='account_reconciliation_list'),
    path('accounts/<int:pk>/reconciliations/add/', views.account_reconciliation_add, name='account_reconciliation_add'),
    path('reconciliations/<int:pk>/complete/', views.reconciliation_complete, name='reconciliation_complete'),

    # Suspense
    path('suspense/', views.suspense_list, name='suspense_list'),
    path('suspense/<int:pk>/allocate/', views.suspense_allocate, name='suspense_allocate'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/export/csv/', views.reports_export_csv, name='reports_export_csv'),
    path('reports/summary/', views.financial_summary, name='financial_summary'),
]
