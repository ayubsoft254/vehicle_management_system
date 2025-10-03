"""
Dashboard App - URL Configuration
Simplified version with only existing views
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Public landing page
    path('', views.landing_page, name='landing'),
    
    # Main dashboard (now at /dashboard/)
    path('dashboard/', views.dashboard_home, name='index'),
    path('<uuid:pk>/', views.dashboard_detail, name='dashboard_detail'),
    
    # Widget management
    path('dashboards/<uuid:dashboard_pk>/widgets/create/', views.widget_create, name='widget_create'),
    path('widgets/<uuid:pk>/edit/', views.widget_update, name='widget_update'),
    path('widgets/<uuid:pk>/delete/', views.widget_delete, name='widget_delete'),
    path('api/widgets/<uuid:pk>/data/', views.widget_data_api, name='widget_data_api'),
    
    # Preferences and settings
    path('preferences/', views.preferences, name='preferences'),
    path('quick-actions/', views.quick_actions, name='quick_actions'),
    
    # Templates and sharing
    path('create-from-template/', views.create_from_template, name='create_from_template'),
    path('dashboards/<uuid:dashboard_pk>/widget-templates/', views.widget_templates, name='widget_templates'),
    path('dashboards/<uuid:dashboard_pk>/add-widget/', views.add_widget_from_template, name='add_widget_from_template'),
    path('<uuid:pk>/share/', views.share_dashboard, name='share_dashboard'),
    
    # Snapshots and analytics
    path('<uuid:pk>/snapshot/', views.create_snapshot, name='create_snapshot'),
    path('analytics/', views.analytics, name='analytics'),
    
    # API endpoints
    path('api/data/', views.dashboard_data_api, name='dashboard_data_api'),
    path('api/financial/', views.financial_data_api, name='financial_data_api'),
]