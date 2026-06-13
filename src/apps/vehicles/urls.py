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
    
    # Selling/Assignment
    path('<int:pk>/sell/', views.sell_vehicle, name='sell'),
    
    # API Endpoints
    path('api/search-clients/', views.search_clients_api, name='search_clients_api'),
    
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
]