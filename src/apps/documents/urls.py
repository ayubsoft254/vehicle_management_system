"""
URL configuration for the documents app.
"""

from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # ========================================================================
    # Document List and Search URLs
    # ========================================================================
    path('', views.document_list, name='document_list'),
    path('search/ajax/', views.ajax_search_documents, name='ajax_search_documents'),
    
    # ========================================================================
    # Document CRUD URLs
    # ========================================================================
    path('create/', views.document_create, name='document_create'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/edit/', views.document_edit, name='document_edit'),
    path('<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('<int:pk>/download/', views.download_document, name='download_document'),
    
    # ========================================================================
    # Sharing URLs
    # ========================================================================
    path('<int:pk>/share/', views.document_share, name='document_share'),
    
    # ========================================================================
    # Category URLs
    # ========================================================================
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
]