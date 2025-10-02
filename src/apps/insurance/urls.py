"""
URL configuration for insurance app
Handles all insurance-related routing
"""
from django.urls import path
from . import views

app_name = 'insurance'

urlpatterns = [
    # ==================== INSURANCE PROVIDER URLS ====================
    
    # Provider List & Views
    path('providers/', views.provider_list, name='provider_list'),
    path('providers/<int:pk>/', views.provider_detail, name='provider_detail'),
    
    # Provider CRUD Operations
    path('providers/create/', views.provider_create, name='provider_create'),
    path('providers/<int:pk>/update/', views.provider_update, name='provider_update'),
    path('providers/<int:pk>/delete/', views.provider_delete, name='provider_delete'),
    
    # ==================== INSURANCE POLICY URLS ====================
    
    # Policy List & Views
    path('', views.policy_list, name='policy_list'),
    path('policies/', views.policy_list, name='policies'),
    path('policies/<int:pk>/', views.policy_detail, name='policy_detail'),
    
    # Policy CRUD Operations
    path('policies/create/', views.policy_create, name='policy_create'),
    path('policies/<int:pk>/update/', views.policy_update, name='policy_update'),
    
    # Policy Actions
    path('policies/<int:pk>/renew/', views.policy_renew, name='policy_renew'),
    path('policies/<int:pk>/cancel/', views.policy_cancel, name='policy_cancel'),
    
    # Expiring Policies
    path('policies/expiring/', views.expiring_policies, name='expiring_policies'),
    
    # ==================== INSURANCE CLAIM URLS ====================
    
    # Claim List & Views
    path('claims/', views.claim_list, name='claim_list'),
    path('claims/<int:pk>/', views.claim_detail, name='claim_detail'),
    
    # Claim CRUD Operations
    path('claims/create/', views.claim_create, name='claim_create'),
    path('claims/<int:pk>/update/', views.claim_update, name='claim_update'),
    
    # ==================== INSURANCE PAYMENT URLS ====================
    
    # Record Payment
    path('policies/<int:policy_pk>/record-payment/', views.payment_create, name='payment_create'),
    
    # ==================== DASHBOARD & REPORTS URLS ====================
    
    # Dashboard
    path('dashboard/', views.insurance_dashboard, name='insurance_dashboard'),
    
    # Reports
    path('reports/', views.insurance_reports, name='insurance_reports'),
    
    # Quote Generator
    path('quote/', views.generate_quote, name='generate_quote'),
    
    # ==================== EXPORT URLS ====================
    
    # CSV Exports
    path('export/policies/csv/', views.export_policies_csv, name='export_policies_csv'),
    path('export/claims/csv/', views.export_claims_csv, name='export_claims_csv'),
    
    # ==================== RELATIONSHIP URLS ====================
    
    # Policies by Entity
    path('policies/vehicle/<int:vehicle_pk>/', views.policies_by_vehicle, name='policies_by_vehicle'),
    path('policies/client/<int:client_pk>/', views.policies_by_client, name='policies_by_client'),
    
    # Claims by Entity
    path('claims/vehicle/<int:vehicle_pk>/', views.claims_by_vehicle, name='claims_by_vehicle'),
    path('claims/client/<int:client_pk>/', views.claims_by_client, name='claims_by_client'),
    
    # ==================== BULK OPERATIONS URLS ====================
    
    # Bulk Reminders
    path('reminders/send-bulk/', views.send_bulk_reminders, name='send_bulk_reminders'),
    
    # Policy Comparison
    path('policies/compare/', views.policy_comparison, name='policy_comparison'),
    
    # ==================== AJAX/API URLS ====================
    
    # API Endpoints for AJAX calls
    path('api/policy-stats/', views.policy_stats_api, name='policy_stats_api'),
    path('api/claim-stats/', views.claim_stats_api, name='claim_stats_api'),
    path('api/expiring-policies/', views.expiring_policies_api, name='expiring_policies_api'),
]