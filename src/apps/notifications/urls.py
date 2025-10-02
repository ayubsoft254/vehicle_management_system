"""
Notifications App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification List & Detail
    path('', views.notification_list, name='notification_list'),
    path('<uuid:pk>/', views.notification_detail, name='notification_detail'),
    path('unread/', views.unread_notifications, name='unread_notifications'),
    
    # Notification Actions
    path('<uuid:pk>/read/', views.mark_as_read, name='mark_as_read'),
    path('<uuid:pk>/unread/', views.mark_as_unread, name='mark_as_unread'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('<uuid:pk>/dismiss/', views.dismiss_notification, name='dismiss_notification'),
    path('<uuid:pk>/delete/', views.delete_notification, name='delete_notification'),
    path('batch-action/', views.batch_action, name='batch_action'),
    
    # Preferences
    path('preferences/', views.notification_preferences, name='preferences'),
    path('toggle/', views.toggle_notifications, name='toggle_notifications'),
    
    # Notification Creation (Admin)
    path('create/', views.create_notification, name='create_notification'),
    path('bulk/', views.bulk_notification, name='bulk_notification'),
    
    # Templates
    path('templates/', views.NotificationTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.NotificationTemplateCreateView.as_view(), name='template_create'),
    path('templates/<uuid:pk>/edit/', views.NotificationTemplateUpdateView.as_view(), name='template_edit'),
    path('templates/<uuid:pk>/delete/', views.NotificationTemplateDeleteView.as_view(), name='template_delete'),
    
    # Schedules
    path('schedules/', views.NotificationScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.NotificationScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<uuid:pk>/edit/', views.NotificationScheduleUpdateView.as_view(), name='schedule_edit'),
    path('schedules/<uuid:pk>/delete/', views.NotificationScheduleDeleteView.as_view(), name='schedule_delete'),
    
    # Dashboard & Analytics
    path('dashboard/', views.notification_dashboard, name='dashboard'),
    path('logs/', views.notification_logs, name='logs'),
    
    # Utility
    path('clear-all/', views.clear_all_notifications, name='clear_all'),
    path('export/', views.export_notifications, name='export_notifications'),
    
    # API Endpoints
    path('api/count/', views.notification_count_api, name='count_api'),
    path('api/recent/', views.recent_notifications_api, name='recent_api'),
    path('api/stats/', views.notification_stats_api, name='stats_api'),
]