"""
URL configuration for the payments app
"""
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment management
    path('', views.payment_list, name='payment_list'),
    path('<int:pk>/', views.payment_detail, name='payment_detail'),
    path('record/<int:client_vehicle_pk>/', views.record_payment, name='record_payment'),
    path('<int:pk>/receipt/', views.payment_receipt, name='payment_receipt'),
    
    # Installment plans
    path('installment-plans/', views.installment_plan_list, name='installment_plan_list'),
    path('installment-plans/<int:pk>/', views.installment_plan_detail, name='installment_plan_detail'),
    path('installment-plans/create/<int:client_vehicle_pk>/', views.create_installment_plan, name='create_installment_plan'),
    path('installment-plans/<int:pk>/update/', views.update_installment_plan, name='update_installment_plan'),
    path('installment-plans/<int:pk>/regenerate/', views.regenerate_payment_schedule, name='regenerate_payment_schedule'),
    
    # Payment schedules
    path('schedules/', views.payment_schedule_list, name='payment_schedule_list'),
    path('overdue/', views.overdue_payments, name='overdue_payments'),
    
    # Reports and analytics
    path('tracker/<int:client_vehicle_pk>/', views.payment_tracker, name='payment_tracker'),
    path('analytics/', views.payment_analytics, name='payment_analytics'),
    path('defaulters/', views.defaulters_report, name='defaulters_report'),
    path('export/csv/', views.export_payments_csv, name='export_payments_csv'),
    
    # API endpoints
    path('api/stats/', views.payment_stats_api, name='payment_stats_api'),
    path('api/chart-data/', views.payment_chart_data_api, name='payment_chart_data_api'),
]