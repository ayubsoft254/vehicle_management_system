"""
Vehicles URL Configuration
"""
from django.urls import path
from . import views

app_name = 'vehicles'

urlpatterns = [
    # Vehicle List & Search
    path('', views.vehicle_list_view, name='list'),
    
    # Vehicle CRUD
    path('create/', views.vehicle_create_view, name='create'),
    path('<int:pk>/', views.vehicle_detail_view, name='detail'),
    path('<int:pk>/edit/', views.vehicle_update_view, name='update'),
    path('<int:pk>/delete/', views.vehicle_delete_view, name='delete'),
    
    # Vehicle Status & Actions
    path('<int:pk>/change-status/', views.vehicle_status_change_view, name='change_status'),
    path('<int:pk>/toggle-featured/', views.vehicle_toggle_featured_view, name='toggle_featured'),
    
    # Photo Management
    path('<int:pk>/upload-photo/', views.vehicle_photo_upload_view, name='upload_photo'),
    path('<int:pk>/photo/<int:photo_pk>/delete/', views.vehicle_photo_delete_view, name='delete_photo'),
    
    # Bulk Actions
    path('bulk-action/', views.bulk_vehicle_action_view, name='bulk_action'),
    
    # Export & Stats
    path('export/', views.vehicle_export_view, name='export'),
    path('stats/', views.vehicle_stats_view, name='stats'),
]