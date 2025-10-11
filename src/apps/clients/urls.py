"""
URL configuration for client app
Handles all client-related routing
"""
from django.urls import path
from . import views, portal_views

app_name = 'clients'

urlpatterns = [
    # ==================== CLIENT PORTAL URLS (For logged-in clients) ====================
    
    # Portal Dashboard
    path('portal/', portal_views.portal_dashboard, name='portal_dashboard'),
    
    # Portal Vehicles
    path('portal/vehicles/', portal_views.portal_vehicles, name='portal_vehicles'),
    path('portal/vehicles/<int:vehicle_id>/', portal_views.portal_vehicle_detail, name='portal_vehicle_detail'),
    
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
    
    # ==================== CLIENT MANAGEMENT URLS (For staff) ====================
    
    # Client List & Search
    path('', views.client_list, name='client_list'),
    path('list/', views.client_list, name='list'),
    
    # Client CRUD Operations
    path('create/', views.client_create, name='client_create'),
    path('<int:pk>/', views.client_detail, name='client_detail'),
    path('<int:pk>/update/', views.client_update, name='client_update'),
    path('<int:pk>/delete/', views.client_delete, name='client_delete'),
    
    # ==================== VEHICLE ASSIGNMENT URLS ====================
    
    # Assign Vehicle to Client
    path('<int:client_pk>/assign-vehicle/', views.assign_vehicle, name='assign_vehicle'),
    
    # Client Vehicle Management
    path('vehicle/<int:pk>/', views.client_vehicle_detail, name='client_vehicle_detail'),
    path('vehicle/<int:pk>/update/', views.client_vehicle_update, name='client_vehicle_update'),
    
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
    
    # ==================== INSTALLMENT PLAN URLS ====================
    
    # Installment Plan Management
    path('vehicle/<int:client_vehicle_pk>/create-installment-plan/', 
         views.create_installment_plan, name='create_installment_plan'),
    
    # ==================== REPORTING & EXPORT URLS ====================
    
    # Client Statement & Reports
    path('<int:client_pk>/statement/', views.client_statement, name='client_statement'),
    path('reports/defaulters/', views.defaulters_report, name='defaulters_report'),
    
    # Export Functions
    path('export/csv/', views.export_clients_csv, name='export_clients_csv'),
    
    # ==================== AJAX/API URLS ====================
    
    # API Endpoints for AJAX calls
    path('api/search/', views.client_search_api, name='client_search_api'),
    path('api/<int:pk>/stats/', views.client_stats_api, name='client_stats_api'),
]