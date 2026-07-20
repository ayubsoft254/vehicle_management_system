"""
URL configuration for client app
Handles all client-related routing
"""
from django.urls import path
from . import views, portal_views, proforma_views

app_name = 'clients'

urlpatterns = [
    # ==================== CLIENT PORTAL URLS (For logged-in clients) ====================
    
    # Portal Dashboard
    path('portal/', portal_views.portal_dashboard, name='portal_dashboard'),
    
    # Portal Vehicles
    path('portal/vehicles/', portal_views.portal_vehicles, name='portal_vehicles'),
    path('portal/vehicles/<int:vehicle_id>/', portal_views.portal_vehicle_detail, name='portal_vehicle_detail'),
    path('portal/vehicles/<int:vehicle_id>/remove/', portal_views.portal_remove_vehicle, name='portal_remove_vehicle'),
    
    # Portal Payments
    path('portal/payments/', portal_views.portal_payments, name='portal_payments'),
    path('portal/payment-schedules/', portal_views.portal_payment_schedules, name='portal_payment_schedules'),
    
    # Portal Installment Plans
    path('portal/installment-plans/', portal_views.portal_installment_plans, name='portal_installment_plans'),
    path('portal/installment-plans/<int:plan_id>/', portal_views.portal_installment_plan_detail, name='portal_installment_plan_detail'),
    
    # Portal Documents
    path('portal/documents/', portal_views.portal_documents, name='portal_documents'),
    path('portal/documents/<int:document_id>/download/', portal_views.portal_document_download, name='portal_document_download'),
    
    # Portal Insurance
    path('portal/insurance/', portal_views.portal_insurance, name='portal_insurance'),
    path('portal/insurance/<int:insurance_id>/', portal_views.portal_insurance_detail, name='portal_insurance_detail'),
    
    # Portal Profile & Settings
    path('portal/profile/', portal_views.portal_profile, name='portal_profile'),
    path('portal/notifications/', portal_views.portal_notifications, name='portal_notifications'),
    
    # Portal Marketplace - Buy Vehicles
    path('portal/marketplace/', portal_views.portal_marketplace, name='portal_marketplace'),
    path('portal/marketplace/<int:vehicle_id>/', portal_views.portal_vehicle_marketplace_detail, name='portal_vehicle_marketplace_detail'),
    path('portal/purchase/<int:vehicle_id>/', portal_views.portal_initiate_purchase, name='portal_initiate_purchase'),
    
    # Portal Payments - Make Payments
    path('portal/make-payment/<int:client_vehicle_id>/<str:payment_type>/', portal_views.portal_make_payment, name='portal_make_payment'),
    path('portal/payment/pending/', portal_views.portal_payment_pending, name='portal_payment_pending'),
    path('portal/payment/status/', portal_views.portal_payment_status, name='portal_payment_status'),
    path('portal/payment/bank-details/<int:client_vehicle_id>/<str:payment_type>/', portal_views.portal_payment_bank_details, name='portal_payment_bank_details'),
    path('portal/payment/bank-details/<int:client_vehicle_id>/<str:payment_type>/pdf/', portal_views.portal_payment_bank_details_pdf, name='portal_payment_bank_details_pdf'),
    
    # Portal Auctions
    path('portal/auctions/', portal_views.portal_auctions, name='portal_auctions'),
    path('portal/auctions/<uuid:auction_id>/', portal_views.portal_auction_detail, name='portal_auction_detail'),
    path('portal/auctions/<uuid:auction_id>/bid/', portal_views.portal_place_bid, name='portal_place_bid'),
    path('portal/auctions/<uuid:auction_id>/register/', portal_views.portal_register_auction, name='portal_register_auction'),
    path('portal/auctions/<uuid:auction_id>/watch/', portal_views.portal_add_to_watchlist, name='portal_add_to_watchlist'),
    path('portal/auctions/<uuid:auction_id>/unwatch/', portal_views.portal_remove_from_watchlist, name='portal_remove_from_watchlist'),
    path('portal/my-bids/', portal_views.portal_my_bids, name='portal_my_bids'),
    path('portal/watchlist/', portal_views.portal_my_watchlist, name='portal_my_watchlist'),
    
    # ==================== CLIENT MANAGEMENT URLS (For staff) ====================
    
    # Client List & Search
    path('', views.client_list, name='client_list'),
    path('list/', views.client_list, name='list'),
    path('trackers/', views.tracker_management, name='tracker_management'),
    
    # Client CRUD Operations
    path('create/', views.client_create, name='client_create'),
    path('<int:pk>/', views.client_detail, name='client_detail'),
    path('<int:pk>/update/', views.client_update, name='client_update'),
    path('<int:pk>/delete/', views.client_delete, name='client_delete'),
    
    # ==================== PROFORMA INVOICES & RESERVATIONS ====================

    path('proformas/', proforma_views.proforma_list, name='proforma_list'),
    path('proformas/create/', proforma_views.proforma_create, name='proforma_create'),
    path('proformas/settings/', proforma_views.reservation_settings, name='reservation_settings'),
    path('proformas/<int:pk>/', proforma_views.proforma_detail, name='proforma_detail'),
    path('proformas/<int:pk>/edit/', proforma_views.proforma_update, name='proforma_update'),
    path('proformas/<int:pk>/pdf/', proforma_views.proforma_pdf, name='proforma_pdf'),
    path('proformas/<int:pk>/issue/', proforma_views.proforma_issue, name='proforma_issue'),
    path('proformas/<int:pk>/cancel/', proforma_views.proforma_cancel, name='proforma_cancel'),
    path('proformas/<int:pk>/confirm-deposit/', proforma_views.confirm_deposit, name='proforma_confirm_deposit'),
    path('proformas/<int:pk>/deposits/<int:deposit_pk>/reverse/', proforma_views.reverse_deposit, name='proforma_reverse_deposit'),
    path('proformas/<int:pk>/deposits/<int:deposit_pk>/receipt/', proforma_views.proforma_deposit_receipt, name='proforma_deposit_receipt'),
    path('proformas/<int:pk>/convert/', proforma_views.convert_proforma, name='proforma_convert'),
    path('reservations/<int:pk>/extend/', proforma_views.reservation_extend, name='reservation_extend'),
    path('reservations/<int:pk>/release/', proforma_views.reservation_release, name='reservation_release'),

    # ==================== VEHICLE ASSIGNMENT URLS ====================
    
    # Assign Vehicle to Client
    path('<int:client_pk>/assign-vehicle/', views.assign_vehicle, name='assign_vehicle'),
    path('vehicle/<int:client_vehicle_pk>/sales-agreement/', views.download_sales_agreement, name='download_sales_agreement'),
    path('vehicle/<int:client_vehicle_pk>/sales-agreement/<int:version_id>/', views.download_sales_agreement, name='download_sales_agreement_version'),
    path('vehicle/<int:pk>/agreement-revision/', views.create_agreement_revision, name='create_agreement_revision'),
    path('vehicle/<int:pk>/sign/', views.sign_agreement_online, name='sign_agreement_online'),

    # Client Vehicle Management
    path('vehicle/<int:pk>/', views.client_vehicle_detail, name='client_vehicle_detail'),
    path('vehicle/<int:pk>/update/', views.client_vehicle_update, name='client_vehicle_update'),
    path('tracker/<int:tracker_pk>/renew/', views.renew_tracker, name='renew_tracker'),
    path('tracker/<int:tracker_pk>/record-payment/', views.record_tracker_payment, name='record_tracker_payment'),
    
    # ==================== PAYMENT URLS ====================
    
    # Payment List & Management
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    
    # Record Payment
    path('vehicle/<int:client_vehicle_pk>/record-payment/', views.record_payment, name='record_payment'),
    
    # ==================== DOCUMENT URLS ====================
    
    # Document Management
    path('<int:client_pk>/documents/', views.document_list, name='document_list'),
    path('<int:client_pk>/upload-document/', views.upload_document, name='upload_document'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('documents/<int:pk>/download/', views.download_client_document, name='download_client_document'),
    
    # ==================== INSTALLMENT PLAN URLS ====================
    
    # Installment Plan Management
    path('vehicle/<int:client_vehicle_pk>/create-installment-plan/', 
         views.create_installment_plan, name='create_installment_plan'),
    
    # ==================== REPORTING & EXPORT URLS ====================
    
    # Client Statement & Reports
    path('ledger/', views.client_ledger_list, name='client_ledger_list'),
    path('ledger/export/<str:fmt>/', views.client_ledger_export, name='client_ledger_export'),
    path('<int:client_pk>/statement/', views.client_statement, name='client_statement'),
    path('<int:client_pk>/statement/export/csv/', views.export_client_ledger_csv, name='export_client_ledger_csv'),
    path('<int:client_pk>/statement/export/excel/', views.export_client_ledger_excel, name='export_client_ledger_excel'),
    path('reports/defaulters/', views.defaulters_report, name='defaulters_report'),
    
    # Export Functions
    path('export/csv/', views.export_clients_csv, name='export_clients_csv'),
    
    # ==================== AJAX/API URLS ====================
    
    # API Endpoints for AJAX calls
    path('api/search/', views.client_search_api, name='client_search_api'),
    path('api/<int:pk>/stats/', views.client_stats_api, name='client_stats_api'),
]