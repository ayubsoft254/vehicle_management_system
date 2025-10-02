"""
URL configuration for the expenses app.
"""

from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # ========================================================================
    # Expense List and Search URLs
    # ========================================================================
    path('', views.expense_list, name='expense_list'),
    path('my-expenses/', views.my_expenses, name='my_expenses'),
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('dashboard/', views.expense_dashboard, name='expense_dashboard'),
    
    # ========================================================================
    # Expense CRUD URLs
    # ========================================================================
    path('create/', views.expense_create, name='expense_create'),
    path('<int:pk>/', views.expense_detail, name='expense_detail'),
    path('<int:pk>/edit/', views.expense_update, name='expense_update'),
    path('<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('<int:pk>/submit/', views.expense_submit, name='expense_submit'),
    
    # ========================================================================
    # Expense Approval URLs
    # ========================================================================
    path('<int:pk>/approve/', views.expense_approve, name='expense_approve'),
    path('<int:pk>/mark-paid/', views.expense_mark_paid, name='expense_mark_paid'),
    
    # ========================================================================
    # Receipt Management URLs
    # ========================================================================
    path('<int:expense_pk>/receipts/upload/', views.receipt_upload, name='receipt_upload'),
    path('receipts/<int:pk>/delete/', views.receipt_delete, name='receipt_delete'),
    
    # ========================================================================
    # Category URLs
    # ========================================================================
    path('categories/', views.category_list, name='category_list'),
    path('categories/<int:pk>/', views.category_expenses, name='category_expenses'),
    
    # ========================================================================
    # Expense Report URLs
    # ========================================================================
    path('reports/', views.report_list, name='report_list'),
    path('reports/create/', views.report_create, name='report_create'),
    path('reports/<int:pk>/', views.report_detail, name='report_detail'),
    path('reports/<int:pk>/add-expenses/', views.report_add_expenses, name='report_add_expenses'),
    
    # ========================================================================
    # Recurring Expense URLs
    # ========================================================================
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/create/', views.recurring_create, name='recurring_create'),
    path('recurring/<int:pk>/generate/', views.recurring_generate, name='recurring_generate'),
    
    # ========================================================================
    # Bulk Actions URLs
    # ========================================================================
    path('bulk-actions/', views.bulk_actions, name='bulk_actions'),
    
    # ========================================================================
    # API/AJAX URLs
    # ========================================================================
    path('api/stats/', views.expense_stats_api, name='expense_stats_api'),
]