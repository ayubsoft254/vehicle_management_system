"""
URL configuration for the repossessions app.
"""

from django.urls import path
from . import views

app_name = 'repossessions'

urlpatterns = [
    # ========================================================================
    # Dashboard
    # ========================================================================
    path('', views.repossession_dashboard, name='repossession_dashboard'),
    
    # ========================================================================
    # Repossession List and Search
    # ========================================================================
    path('list/', views.repossession_list, name='repossession_list'),
    
    # ========================================================================
    # Repossession CRUD URLs
    # ========================================================================
    path('create/', views.repossession_create, name='repossession_create'),
    path('<int:pk>/', views.repossession_detail, name='repossession_detail'),
    path('<int:pk>/edit/', views.repossession_update, name='repossession_update'),
    path('<int:pk>/delete/', views.repossession_delete, name='repossession_delete'),
    
    # ========================================================================
    # Status Management URLs
    # ========================================================================
    path('<int:pk>/status/', views.repossession_update_status, name='repossession_update_status'),
    path('<int:pk>/complete/', views.repossession_complete, name='repossession_complete'),
    
    # ========================================================================
    # Document Management URLs
    # ========================================================================
    path('<int:repossession_pk>/documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    
    # ========================================================================
    # Notes Management URLs
    # ========================================================================
    path('<int:repossession_pk>/notes/create/', views.note_create, name='note_create'),
    path('notes/<int:pk>/delete/', views.note_delete, name='note_delete'),
    
    # ========================================================================
    # Expense Management URLs
    # ========================================================================
    path('<int:repossession_pk>/expenses/create/', views.expense_create, name='expense_create'),
    
    # ========================================================================
    # Notice Management URLs
    # ========================================================================
    path('<int:repossession_pk>/notices/create/', views.notice_create, name='notice_create'),
    path('notices/<int:pk>/mark-delivered/', views.notice_mark_delivered, name='notice_mark_delivered'),
    
    # ========================================================================
    # Contact Management URLs
    # ========================================================================
    path('<int:repossession_pk>/contacts/create/', views.contact_create, name='contact_create'),
    
    # ========================================================================
    # Recovery Attempt URLs
    # ========================================================================
    path('<int:repossession_pk>/recovery-attempts/create/', views.recovery_attempt_create, name='recovery_attempt_create'),
    
    # ========================================================================
    # Reports URLs
    # ========================================================================
    path('reports/', views.repossession_reports, name='repossession_reports'),
    
    # ========================================================================
    # API/AJAX URLs
    # ========================================================================
    path('<int:pk>/timeline/', views.repossession_timeline, name='repossession_timeline'),
]