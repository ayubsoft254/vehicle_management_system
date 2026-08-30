"""
URL configuration for the payments app
"""
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment management
    path('', views.payment_list, name='payment_list'),
    path('<int:pk>/', views.payment_detail, name='payment_detail'),
    path('<int:pk>/reverse/', views.reverse_payment, name='reverse_payment'),
    path('quick-record/', views.quick_record_payment, name='quick_record_payment'),
    path('record/<int:client_vehicle_pk>/', views.record_payment, name='record_payment'),
    path('withdrawals/new/', views.record_account_withdrawal, name='record_account_withdrawal'),
    path('withdrawals/', views.account_withdrawal_list, name='account_withdrawal_list'),
    path('accounts/<str:method>/transactions/', views.account_transactions, name='account_transactions'),
    path('<int:pk>/receipt/', views.payment_receipt, name='payment_receipt'),
    path('<int:pk>/receipt/pdf/', views.payment_receipt_pdf, name='payment_receipt_pdf'),

    # Finance account breakdown (full pages)
    path('accounts/hoza/', views.account_breakdown, {'category': 'hoza'}, name='hoza_account_breakdown'),
    path('accounts/ke/', views.account_breakdown, {'category': 'ke'}, name='ke_account_breakdown'),
    path('accounts/other/', views.account_breakdown, {'category': 'other'}, name='other_account_breakdown'),
    path('accounts/new/', views.account_create, name='account_create'),
    path('accounts/transfer/', views.account_transfer_create, name='account_transfer_create'),
    path('accounts/<int:pk>/detail/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/detail/pdf/', views.account_detail_pdf, name='account_detail_pdf'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<int:pk>/deactivate/', views.account_deactivate, name='account_deactivate'),
    path('accounts/<int:pk>/activate/', views.account_activate, name='account_activate'),
    path('accounts/<int:pk>/transactions/new/', views.account_transaction_create, name='account_transaction_create'),

    # Approvals and reconciliation
    path('approvals/', views.approval_queue, name='approval_queue'),
    path('accounts/transactions/<int:pk>/approve/', views.account_transaction_approve, name='account_transaction_approve'),
    path('accounts/transactions/<int:pk>/reject/', views.account_transaction_reject, name='account_transaction_reject'),
    path('accounts/transactions/<int:transaction_pk>/reconcile/', views.reconciliation_create, name='reconciliation_create'),
    path('accounts/transfers/<int:pk>/approve/', views.account_transfer_approve, name='account_transfer_approve'),
    path('accounts/transfers/<int:pk>/reject/', views.account_transfer_reject, name='account_transfer_reject'),
    path('reconciliations/<int:pk>/approve/', views.reconciliation_approve, name='reconciliation_approve'),
    path('reconciliations/<int:pk>/reject/', views.reconciliation_reject, name='reconciliation_reject'),

    # Installment plans
    path('installment-plans/', views.installment_plan_list, name='installment_plan_list'),
    path('installment-plans/<int:pk>/', views.installment_plan_detail, name='installment_plan_detail'),
    path('installment-plans/create/<int:client_vehicle_pk>/', views.create_installment_plan, name='create_installment_plan'),
    path('installment-plans/<int:pk>/update/', views.update_installment_plan, name='update_installment_plan'),
    path('installment-plans/<int:pk>/extend/', views.extend_installment_plan, name='extend_installment_plan'),
    path('installment-plans/<int:pk>/regenerate/', views.regenerate_payment_schedule, name='regenerate_payment_schedule'),
    
    # Payment schedules
    path('schedules/', views.payment_schedule_list, name='payment_schedule_list'),
    path('overdue/', views.overdue_payments, name='overdue_payments'),
    
    # Reports and analytics
    path('tracker/<int:client_vehicle_pk>/', views.payment_tracker, name='payment_tracker'),
    path('analytics/', views.payment_analytics, name='payment_analytics'),
    path('paybill/', views.paybill_tracker, name='paybill_tracker'),
    path('paybill/export/pdf/', views.paybill_tracker_pdf, name='paybill_tracker_pdf'),
    path('paybill/refresh-balance/', views.refresh_paybill_balance, name='refresh_paybill_balance'),
    path('paybill/register-c2b/', views.register_paybill_c2b, name='register_paybill_c2b'),
    path('paybill/update-security-credential/', views.update_mpesa_security_credential, name='update_mpesa_security_credential'),
    path('defaulters/', views.defaulters_report_view, name='defaulters_report'),
    path('defaulters/export/<str:fmt>/', views.defaulters_report_export, name='defaulters_report_export'),
    path('export/csv/', views.export_payments_csv, name='export_payments_csv'),
    path('export/pdf/agreement/<int:client_vehicle_pk>/', views.generate_agreement_pdf_view, name='generate_agreement_pdf'),
    path('export/pdf/proforma/<int:client_vehicle_pk>/', views.generate_proforma_invoice_pdf_view, name='generate_proforma_invoice_pdf'),
    path('export/pdf/tracker/<int:client_vehicle_pk>/', views.generate_payment_tracker_pdf_view, name='generate_payment_tracker_pdf'),
    path('clients/<int:client_pk>/statement/pdf/', views.client_statement_pdf_view, name='client_statement_pdf'),
    path('<int:payment_pk>/reconcile/', views.payment_reconciliation_create, name='payment_reconciliation_create'),

    # Daraja callbacks
    path('paybill/callbacks/validation/', views.paybill_validation_callback, name='paybill_validation_callback'),
    path('paybill/callbacks/confirmation/', views.paybill_confirmation_callback, name='paybill_confirmation_callback'),
    path('mpesa-callback/', views.stk_push_callback, name='stk_push_callback'),
    path('paybill/callbacks/balance-result/', views.paybill_balance_result_callback, name='paybill_balance_result_callback'),
    path('paybill/callbacks/balance-timeout/', views.paybill_balance_timeout_callback, name='paybill_balance_timeout_callback'),

    # Slash-less aliases for the Daraja callbacks. Safaricom POSTs to the
    # exact URL registered with it — historically registered without a
    # trailing slash — and Django cannot redirect a POST to append the slash
    # (APPEND_SLASH raises instead), so every such callback 500s and the
    # transaction is lost. Accept both forms.
    path('paybill/callbacks/validation', views.paybill_validation_callback),
    path('paybill/callbacks/confirmation', views.paybill_confirmation_callback),
    path('mpesa-callback', views.stk_push_callback),
    path('paybill/callbacks/balance-result', views.paybill_balance_result_callback),
    path('paybill/callbacks/balance-timeout', views.paybill_balance_timeout_callback),

    # Secondary paybill (paybill2 / MPESA_SHORTCODE_2) callback URLs — same
    # views as above, since they identify the paybill from BusinessShortCode
    # in the payload rather than the URL. Kept as separate paths because the
    # secondary paybill is registered with Safaricom under its own domain
    # (see MPESA_*_URL_2 in .env). Both slash forms accepted for the same
    # reason as above.
    path('paybill2/callbacks/validation/', views.paybill_validation_callback, name='paybill_validation_callback_2'),
    path('paybill2/callbacks/confirmation/', views.paybill_confirmation_callback, name='paybill_confirmation_callback_2'),
    path('mpesa-callback2/', views.stk_push_callback, name='stk_push_callback_2'),
    path('paybill2/callbacks/balance-result/', views.paybill_balance_result_callback, name='paybill_balance_result_callback_2'),
    path('paybill2/callbacks/balance-timeout/', views.paybill_balance_timeout_callback, name='paybill_balance_timeout_callback_2'),
    path('paybill2/callbacks/validation', views.paybill_validation_callback),
    path('paybill2/callbacks/confirmation', views.paybill_confirmation_callback),
    path('mpesa-callback2', views.stk_push_callback),
    path('paybill2/callbacks/balance-result', views.paybill_balance_result_callback),
    path('paybill2/callbacks/balance-timeout', views.paybill_balance_timeout_callback),

    # API endpoints
    path('api/stats/', views.payment_stats_api, name='payment_stats_api'),
    path('api/chart-data/', views.payment_chart_data_api, name='payment_chart_data_api'),
    path('api/due-monitor/', views.due_monitor_api, name='due_monitor_api'),

    # Staff STK Push AJAX
    path('api/stk-push/<int:client_vehicle_pk>/', views.staff_stk_initiate, name='staff_stk_initiate'),
    path('api/stk-status/', views.staff_stk_status, name='staff_stk_status'),
]