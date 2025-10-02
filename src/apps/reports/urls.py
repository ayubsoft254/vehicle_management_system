"""
Reports App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Report List & Dashboard
    path('', views.report_list, name='report_list'),
    path('dashboard/', views.report_dashboard, name='dashboard'),
    
    # Report CRUD
    path('create/', views.ReportCreateView.as_view(), name='report_create'),
    path('<uuid:pk>/', views.report_detail, name='report_detail'),
    path('<uuid:pk>/edit/', views.ReportUpdateView.as_view(), name='report_edit'),
    path('<uuid:pk>/delete/', views.ReportDeleteView.as_view(), name='report_delete'),
    
    # Report Execution
    path('<uuid:pk>/run/', views.run_report, name='run_report'),
    path('execution/<uuid:pk>/', views.execution_detail, name='execution_detail'),
    path('execution/<uuid:pk>/download/', views.download_report, name='download_report'),
    path('executions/', views.execution_list, name='execution_list'),
    
    # Report Scheduling
    path('<uuid:pk>/schedule/', views.schedule_report, name='schedule_report'),
    path('<uuid:pk>/unschedule/', views.unschedule_report, name='unschedule_report'),
    
    # Saved Reports
    path('<uuid:pk>/save/', views.save_report, name='save_report'),
    path('<uuid:pk>/unsave/', views.unsave_report, name='unsave_report'),
    path('my-reports/', views.my_reports, name='my_reports'),
    
    # Report Templates
    path('templates/', views.ReportTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.ReportTemplateCreateView.as_view(), name='template_create'),
    path('templates/<uuid:pk>/edit/', views.ReportTemplateUpdateView.as_view(), name='template_edit'),
    path('templates/<uuid:pk>/delete/', views.ReportTemplateDeleteView.as_view(), name='template_delete'),
    
    # Report Builder
    path('builder/', views.report_builder, name='report_builder'),
    
    # Widgets
    path('widgets/', views.widget_list, name='widget_list'),
    path('widgets/<uuid:pk>/data/', views.widget_data, name='widget_data'),
    
    # Analytics
    path('analytics/', views.report_analytics, name='analytics'),
    
    # Export & Sharing
    path('<uuid:pk>/export-config/', views.export_report_config, name='export_config'),
    
    # API Endpoints
    path('api/types/', views.report_types_api, name='types_api'),
    path('api/<uuid:pk>/stats/', views.report_stats_api, name='stats_api'),
    path('api/execution/<uuid:pk>/status/', views.execution_status_api, name='execution_status_api'),
]
