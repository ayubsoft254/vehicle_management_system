"""
Dashboard App - URL Configuration
Simplified version with only existing views
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Public landing page with vehicle showcase
    path('', views.landing_page, name='landing'),
    
    # Public vehicle views (no login required)
    # Changed from 'vehicles/<int:pk>/' to 'vehicle/<int:pk>/' to avoid conflict with vehicles app
    path('vehicle/<int:pk>/', views.public_vehicle_detail, name='public_vehicle_detail'),
    path('purchase-vehicle/<int:pk>/', views.public_vehicle_purchase, name='public_vehicle_purchase'),
    
    # Main dashboard (now at /dashboard/)
    # Keep existing 'index' name and also provide a 'home' alias for backwards compatibility
    path('dashboard/', views.dashboard_home, name='index'),
    path('dashboard/', views.dashboard_home, name='home'),
    
    # Dashboard CRUD operations
    path('dashboards/', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/create/', views.DashboardCreateView.as_view(), name='dashboard_create'),
    path('dashboards/<uuid:pk>/', views.dashboard_detail, name='dashboard_detail'),
    path('dashboards/<uuid:pk>/update/', views.DashboardUpdateView.as_view(), name='dashboard_update'),
    path('dashboards/<uuid:pk>/delete/', views.DashboardDeleteView.as_view(), name='dashboard_delete'),
    path('dashboards/<uuid:pk>/export/', views.export_dashboard, name='export_dashboard'),
    path('dashboards/<uuid:pk>/set-default/', views.set_default_dashboard, name='set_default_dashboard'),
    path('dashboards/<uuid:pk>/share/', views.share_dashboard, name='share_dashboard'),
    path('dashboards/<uuid:pk>/snapshot/', views.create_snapshot, name='create_snapshot'),
    
    # Widget management (COMMENTED OUT)
    # path('dashboards/<uuid:dashboard_pk>/widgets/create/', views.widget_create, name='widget_create'),
    # path('dashboards/<uuid:dashboard_pk>/widget-templates/', views.widget_templates, name='widget_templates'),
    # path('dashboards/<uuid:dashboard_pk>/add-widget/', views.add_widget_from_template, name='add_widget_from_template'),
    # path('widgets/<uuid:pk>/edit/', views.widget_update, name='widget_update'),
    # path('widgets/<uuid:pk>/delete/', views.widget_delete, name='widget_delete'),
    # path('widgets/<uuid:pk>/data/', views.widget_data_api, name='widget_data_api'),
    
    # Quick actions
    # path('preferences/', views.preferences, name='preferences'),
    path('quick-actions/', views.quick_actions, name='quick_actions'),
    
    # Templates
    path('create-from-template/', views.create_from_template, name='create_from_template'),
    
    # Analytics
    path('analytics/', views.analytics, name='analytics'),
    
    # API endpoints
    path('api/data/', views.dashboard_data_api, name='dashboard_data_api'),
    path('api/financial/', views.financial_data_api, name='financial_data_api'),
    # path('api/widgets/position/', views.update_widget_position, name='update_widget_position'),
]