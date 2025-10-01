"""
URL configuration for audit app
Handles audit log viewing, filtering, and exporting
"""
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Dashboard / List Views
    path('', views.audit_log_list, name='log_list'),
    path('logs/', views.audit_log_list, name='audit_logs'),
    
    # Detail View
    path('logs/<int:pk>/', views.audit_log_detail, name='log_detail'),
    
    # Filtered Views
    path('logs/user/<int:user_id>/', views.audit_logs_by_user, name='logs_by_user'),
    path('logs/action/<str:action_type>/', views.audit_logs_by_action, name='logs_by_action'),
    path('logs/date-range/', views.audit_logs_by_date_range, name='logs_by_date_range'),
    path('logs/model/<str:model_name>/', views.audit_logs_by_model, name='logs_by_model'),
    
    # Export Endpoints
    path('export/csv/', views.export_audit_logs_csv, name='export_csv'),
    path('export/pdf/', views.export_audit_logs_pdf, name='export_pdf'),
    path('export/excel/', views.export_audit_logs_excel, name='export_excel'),
    
    # Search & Filter
    path('search/', views.audit_log_search, name='search'),
    path('advanced-filter/', views.audit_log_advanced_filter, name='advanced_filter'),
    
    # Analytics & Reports
    path('analytics/', views.audit_analytics, name='analytics'),
    path('analytics/user-activity/', views.user_activity_report, name='user_activity'),
    path('analytics/system-activity/', views.system_activity_report, name='system_activity'),
    path('analytics/by-module/', views.activity_by_module, name='activity_by_module'),
    
    # Compliance & Security
    path('compliance-report/', views.compliance_report, name='compliance_report'),
    path('security-events/', views.security_events, name='security_events'),
    path('failed-logins/', views.failed_login_attempts, name='failed_logins'),
    
    # Settings & Configuration
    path('settings/', views.audit_settings, name='settings'),
    path('retention-policy/', views.retention_policy, name='retention_policy'),
    
    # Bulk Operations
    path('bulk-delete/', views.bulk_delete_logs, name='bulk_delete'),
    path('archive/', views.archive_old_logs, name='archive_logs'),
    
    # API Endpoints (for AJAX calls)
    path('api/recent-activities/', views.recent_activities_api, name='recent_activities_api'),
    path('api/activity-chart/', views.activity_chart_data, name='activity_chart_data'),
    path('api/log-count/', views.log_count_api, name='log_count_api'),
]