"""
Dashboard App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ============================================================================
    # MAIN DASHBOARD VIEWS
    # ============================================================================
    
    # Main dashboard index
    path('', views.dashboard_index, name='index'),
    
    # Custom dashboards
    path('custom/', views.dashboard_list, name='dashboard_list'),
    path('custom/create/', views.dashboard_create, name='dashboard_create'),
    path('custom/<uuid:pk>/', views.dashboard_detail, name='dashboard_detail'),
    path('custom/<uuid:pk>/edit/', views.dashboard_update, name='dashboard_update'),
    path('custom/<uuid:pk>/delete/', views.dashboard_delete, name='dashboard_delete'),
    path('custom/<uuid:pk>/duplicate/', views.dashboard_duplicate, name='dashboard_duplicate'),
    path('custom/<uuid:pk>/set-default/', views.set_default_dashboard, name='set_default_dashboard'),
    
    # ============================================================================
    # WIDGET MANAGEMENT
    # ============================================================================
    
    # Widget CRUD
    path('widgets/', views.widget_list, name='widget_list'),
    path('widgets/create/', views.widget_create, name='widget_create'),
    path('widgets/<uuid:pk>/', views.widget_detail, name='widget_detail'),
    path('widgets/<uuid:pk>/edit/', views.widget_update, name='widget_update'),
    path('widgets/<uuid:pk>/delete/', views.widget_delete, name='widget_delete'),
    path('widgets/<uuid:pk>/duplicate/', views.widget_duplicate, name='widget_duplicate'),
    
    # Widget operations
    path('widgets/<uuid:pk>/toggle/', views.toggle_widget, name='toggle_widget'),
    path('widgets/<uuid:pk>/refresh/', views.refresh_widget, name='refresh_widget'),
    path('widgets/<uuid:pk>/data/', views.widget_data, name='widget_data'),
    path('widgets/reorder/', views.reorder_widgets, name='reorder_widgets'),
    
    # ============================================================================
    # ANALYTICS & METRICS
    # ============================================================================
    
    # Overview analytics
    path('analytics/', views.analytics_overview, name='analytics_overview'),
    path('analytics/vehicles/', views.vehicle_analytics, name='vehicle_analytics'),
    path('analytics/clients/', views.client_analytics, name='client_analytics'),
    path('analytics/financial/', views.financial_analytics, name='financial_analytics'),
    path('analytics/sales/', views.sales_analytics, name='sales_analytics'),
    
    # Metrics API
    path('api/metrics/overview/', views.metrics_overview_api, name='metrics_overview_api'),
    path('api/metrics/vehicles/', views.vehicle_metrics_api, name='vehicle_metrics_api'),
    path('api/metrics/payments/', views.payment_metrics_api, name='payment_metrics_api'),
    path('api/metrics/clients/', views.client_metrics_api, name='client_metrics_api'),
    path('api/metrics/trends/', views.trend_metrics_api, name='trend_metrics_api'),
    
    # ============================================================================
    # QUICK ACTIONS
    # ============================================================================
    
    # Quick action management
    path('quick-actions/', views.quick_action_list, name='quick_action_list'),
    path('quick-actions/create/', views.quick_action_create, name='quick_action_create'),
    path('quick-actions/<uuid:pk>/edit/', views.quick_action_update, name='quick_action_update'),
    path('quick-actions/<uuid:pk>/delete/', views.quick_action_delete, name='quick_action_delete'),
    path('quick-actions/reorder/', views.reorder_quick_actions, name='reorder_quick_actions'),
    
    # ============================================================================
    # USER PREFERENCES
    # ============================================================================
    
    # Dashboard preferences
    path('preferences/', views.dashboard_preferences, name='preferences'),
    path('preferences/update/', views.update_preferences, name='update_preferences'),
    path('preferences/reset/', views.reset_preferences, name='reset_preferences'),
    
    # Theme and layout
    path('preferences/theme/', views.update_theme, name='update_theme'),
    path('preferences/layout/', views.update_layout, name='update_layout'),
    
    # ============================================================================
    # DASHBOARD SHARING & COLLABORATION
    # ============================================================================
    
    # Share dashboard
    path('custom/<uuid:pk>/share/', views.share_dashboard, name='share_dashboard'),
    path('custom/<uuid:pk>/unshare/', views.unshare_dashboard, name='unshare_dashboard'),
    path('custom/<uuid:pk>/permissions/', views.dashboard_permissions, name='dashboard_permissions'),
    
    # ============================================================================
    # SNAPSHOTS & EXPORTS
    # ============================================================================
    
    # Dashboard snapshots
    path('snapshots/', views.snapshot_list, name='snapshot_list'),
    path('snapshots/create/', views.create_snapshot, name='create_snapshot'),
    path('snapshots/<uuid:pk>/', views.snapshot_detail, name='snapshot_detail'),
    path('snapshots/<uuid:pk>/delete/', views.snapshot_delete, name='snapshot_delete'),
    path('snapshots/<uuid:pk>/restore/', views.restore_snapshot, name='restore_snapshot'),
    
    # Export options
    path('export/pdf/', views.export_dashboard_pdf, name='export_pdf'),
    path('export/excel/', views.export_dashboard_excel, name='export_excel'),
    path('export/json/', views.export_dashboard_json, name='export_json'),
    
    # ============================================================================
    # ACTIVITY & HISTORY
    # ============================================================================
    
    # Dashboard activity
    path('activity/', views.dashboard_activity, name='activity'),
    path('activity/clear/', views.clear_activity, name='clear_activity'),
    
    # Recent items
    path('recent/vehicles/', views.recent_vehicles, name='recent_vehicles'),
    path('recent/clients/', views.recent_clients, name='recent_clients'),
    path('recent/payments/', views.recent_payments, name='recent_payments'),
    
    # ============================================================================
    # NOTIFICATIONS & ALERTS
    # ============================================================================
    
    # Dashboard notifications
    path('notifications/', views.dashboard_notifications, name='notifications'),
    path('notifications/<int:pk>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Alerts
    path('alerts/', views.dashboard_alerts, name='alerts'),
    path('alerts/<int:pk>/dismiss/', views.dismiss_alert, name='dismiss_alert'),
    
    # ============================================================================
    # SEARCH & FILTERS
    # ============================================================================
    
    # Global search
    path('search/', views.global_search, name='global_search'),
    path('search/advanced/', views.advanced_search, name='advanced_search'),
    path('api/search/', views.search_api, name='search_api'),
    
    # Saved filters
    path('filters/', views.saved_filters, name='saved_filters'),
    path('filters/save/', views.save_filter, name='save_filter'),
    path('filters/<int:pk>/delete/', views.delete_filter, name='delete_filter'),
    
    # ============================================================================
    # REPORTS INTEGRATION
    # ============================================================================
    
    # Quick reports
    path('reports/quick/', views.quick_reports, name='quick_reports'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/scheduled/', views.scheduled_reports, name='scheduled_reports'),
    
    # ============================================================================
    # HELP & SUPPORT
    # ============================================================================
    
    # Dashboard help
    path('help/', views.dashboard_help, name='help'),
    path('help/tour/', views.dashboard_tour, name='tour'),
    path('help/shortcuts/', views.keyboard_shortcuts, name='shortcuts'),
    
    # ============================================================================
    # SETTINGS & CONFIGURATION
    # ============================================================================
    
    # Dashboard settings
    path('settings/', views.dashboard_settings, name='settings'),
    path('settings/widgets/', views.widget_settings, name='widget_settings'),
    path('settings/notifications/', views.notification_settings, name='notification_settings'),
    
    # ============================================================================
    # ADMIN & MAINTENANCE
    # ============================================================================
    
    # Cache management
    path('admin/cache/clear/', views.clear_cache, name='clear_cache'),
    path('admin/cache/refresh/', views.refresh_cache, name='refresh_cache'),
    
    # System status
    path('admin/status/', views.system_status, name='system_status'),
    path('admin/metrics/', views.system_metrics, name='system_metrics'),
    
    # ============================================================================
    # AJAX/API ENDPOINTS
    # ============================================================================
    
    # Widget data endpoints
    path('api/widgets/<uuid:pk>/data/', views.widget_data_api, name='widget_data_api'),
    path('api/widgets/bulk-update/', views.bulk_update_widgets, name='bulk_update_widgets'),
    
    # Chart data endpoints
    path('api/charts/sales/', views.sales_chart_data, name='sales_chart_data'),
    path('api/charts/revenue/', views.revenue_chart_data, name='revenue_chart_data'),
    path('api/charts/inventory/', views.inventory_chart_data, name='inventory_chart_data'),
    path('api/charts/performance/', views.performance_chart_data, name='performance_chart_data'),
    
    # Statistics endpoints
    path('api/stats/summary/', views.summary_stats_api, name='summary_stats_api'),
    path('api/stats/comparison/', views.comparison_stats_api, name='comparison_stats_api'),
    path('api/stats/trends/', views.trend_stats_api, name='trend_stats_api'),
    
    # Real-time updates
    path('api/realtime/updates/', views.realtime_updates, name='realtime_updates'),
    path('api/realtime/notifications/', views.realtime_notifications, name='realtime_notifications'),
]