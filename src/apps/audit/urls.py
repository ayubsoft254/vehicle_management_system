"""
URL configuration for audit app
Handles audit log viewing, filtering, and exporting
"""
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Dashboard / List Views
    path('', views.audit_list_view, name='log_list'),
    path('logs/', views.audit_list_view, name='audit_logs'),
    
    # Detail View
    path('logs/<int:pk>/', views.audit_detail_view, name='log_detail'),
    
    # User Activity
    path('user/<int:user_id>/', views.user_activity_view, name='user_activity'),
    
    # Export
    path('export/', views.audit_export_view, name='export_csv'),

    # Summary Report
    path('report/', views.audit_report, name='report'),
    path('report/export/pdf/', views.audit_report_pdf, name='report_pdf'),
    path('report/export/excel/', views.audit_report_excel, name='report_excel'),
    path('report/export/csv/', views.audit_report_csv, name='report_csv'),

    # Login History
    path('logins/', views.login_history_view, name='login_history'),
    
    # Dashboard Stats (AJAX)
    path('api/stats/', views.dashboard_stats_view, name='dashboard_stats'),
    
    # Cleanup (Admin only)
    path('cleanup/', views.audit_cleanup_view, name='cleanup'),
]