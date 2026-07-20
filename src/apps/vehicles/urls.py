"""
Vehicles URL Configuration
"""
from django.urls import path
from . import views

app_name = 'vehicles'

urlpatterns = [
    # Vehicle List & Search
    path('', views.vehicle_list_view, name='list'),
    path('purchase-pricing/', views.vehicle_purchase_price_assignment_view, name='purchase_price_assignment'),
    
    # Vehicle CRUD
    path('create/', views.vehicle_create_view, name='create'),
    path('<int:pk>/', views.vehicle_detail_view, name='detail'),
    path('<int:pk>/edit/', views.vehicle_update_view, name='update'),
    path('<int:pk>/move/', views.vehicle_move_view, name='move'),
    path('<int:pk>/delete/', views.vehicle_delete_view, name='delete'),
    
    # Vehicle Status & Actions
    path('<int:pk>/change-status/', views.vehicle_status_change_view, name='change_status'),
    path('<int:pk>/toggle-featured/', views.vehicle_toggle_featured_view, name='toggle_featured'),
    
    # Photo Management
    path('<int:pk>/upload-photo/', views.vehicle_photo_upload_view, name='upload_photo'),
    path('<int:pk>/photo/<int:photo_pk>/delete/', views.vehicle_photo_delete_view, name='delete_photo'),
    path('<int:pk>/photo/<int:photo_pk>/update/', views.vehicle_photo_update_view, name='update_photo'),
    path('<int:pk>/toggle-photo-downloads/', views.vehicle_toggle_photo_downloads_view, name='toggle_photo_downloads'),
    
    # Selling/Assignment
    path('<int:pk>/sell/', views.sell_vehicle, name='sell'),
    
    # API Endpoints
    path('api/search-clients/', views.search_clients_api, name='search_clients_api'),
    path('api/pricing/<int:pk>/', views.vehicle_pricing_api, name='pricing_api'),
    
    # Bulk Actions
    path('bulk-action/', views.bulk_vehicle_action_view, name='bulk_action'),
    
    # Export & Stats
    path('export/', views.vehicle_export_view, name='export'),
    path('stats/', views.vehicle_stats_view, name='stats'),
    path('reports/', views.vehicle_reports, name='vehicle_reports'),

    # Tracker Agent Ledger
    path('tracker-agents/', views.tracker_agent_ledger_list, name='tracker_agent_ledger_list'),
    path('tracker-agents/<int:pk>/', views.tracker_agent_ledger_detail, name='tracker_agent_ledger_detail'),
    path('tracker-records/<int:pk>/mark-paid/', views.tracker_record_mark_paid, name='tracker_record_mark_paid'),
    path('tracker-agents/<int:agent_pk>/mark-all-paid/', views.tracker_agent_mark_all_paid, name='tracker_agent_mark_all_paid'),

    # Clearing Agent Ledger
    path('clearing-agents/', views.clearing_agent_ledger_list, name='clearing_agent_ledger_list'),
    path('clearing-agents/<int:pk>/', views.clearing_agent_ledger_detail, name='clearing_agent_ledger_detail'),
    path('clearance-records/<int:pk>/mark-paid/', views.clearance_record_mark_paid, name='clearance_record_mark_paid'),
    path('clearing-agents/<int:agent_pk>/mark-all-paid/', views.clearing_agent_mark_all_paid, name='clearing_agent_mark_all_paid'),
    path('tracker-agents/<int:agent_pk>/record-payment/', views.record_tracker_agent_payment, name='record_tracker_agent_payment'),
    path('clearing-agents/<int:agent_pk>/record-payment/', views.record_clearing_agent_payment, name='record_clearing_agent_payment'),

    # Japan Supplier Ledger
    path('japan-suppliers/', views.japan_supplier_ledger_list, name='japan_supplier_ledger_list'),
    path('japan-suppliers/<int:pk>/', views.japan_supplier_ledger_detail, name='japan_supplier_ledger_detail'),
    path('japan-supplier-records/<int:pk>/mark-paid/', views.japan_supplier_record_mark_paid, name='japan_supplier_record_mark_paid'),
    path('japan-suppliers/<int:supplier_pk>/mark-all-paid/', views.japan_supplier_mark_all_paid, name='japan_supplier_mark_all_paid'),
    path('japan-suppliers/<int:supplier_pk>/record-payment/', views.record_japan_supplier_payment, name='record_japan_supplier_payment'),
    path('japan-suppliers/<int:pk>/delete/', views.delete_japan_supplier, name='delete_japan_supplier'),

    # Main Ledger
    path('main-ledger/', views.main_ledger_view, name='main_ledger'),
    path('main-ledger/export/<str:fmt>/', views.main_ledger_export, name='main_ledger_export'),

    # Sales Ledger
    path('sales-ledger/', views.sales_ledger, name='sales_ledger'),
    path('sales-ledger/export/<str:fmt>/', views.sales_ledger_export, name='sales_ledger_export'),

    # Partner ledger exports (broker/tracker_agent/clearing_agent/japan_supplier x pdf/excel/csv)
    path('ledgers/<str:kind>/export/<str:fmt>/', views.party_ledger_export, name='party_ledger_export'),

    # Broker Ledger
    path('brokers/', views.broker_ledger_list, name='broker_ledger_list'),
    path('brokers/<int:pk>/', views.broker_ledger_detail, name='broker_ledger_detail'),
    path('brokers/<int:broker_pk>/mark-all-paid/', views.broker_mark_all_paid, name='broker_mark_all_paid'),
    path('brokers/<int:broker_pk>/record-payment/', views.record_broker_payment, name='record_broker_payment'),
    path('broker-sales/<int:pk>/mark-paid/', views.broker_commission_mark_paid, name='broker_commission_mark_paid'),
    path('broker-payments/<int:payment_pk>/voucher/', views.broker_voucher_print, name='broker_voucher_print'),

    # Business Loans (money loaned out by the business)
    path('business-loans/', views.business_loan_list, name='business_loan_list'),
    path('business-loans/export/<str:fmt>/', views.business_loan_export, name='business_loan_export'),
    path('business-loans/<int:pk>/', views.business_loan_detail, name='business_loan_detail'),
    path('business-loans/<int:loan_pk>/record-repayment/', views.record_loan_repayment, name='record_loan_repayment'),
    path('business-loans/<int:pk>/write-off/', views.business_loan_write_off, name='business_loan_write_off'),
]