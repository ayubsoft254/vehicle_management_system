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
    path('my-documents/', views.my_documents, name='my_documents'),
    path('shared/', views.shared_with_me, name='shared_with_me'),
    path('archived/', views.archived_documents, name='archived_documents'),
    path('search/', views.quick_search, name='quick_search'),
    
    # ========================================================================
    # Document CRUD URLs
    # ========================================================================
    path('create/', views.document_create, name='document_create'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/edit/', views.document_update, name='document_update'),
    path('<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('<int:pk>/archive/', views.document_archive, name='document_archive'),
    path('<int:pk>/download/', views.document_download, name='document_download'),
    path('<int:pk>/preview/', views.document_preview, name='document_preview'),
    
    # ========================================================================
    # Version Control URLs
    # ========================================================================
    path('<int:document_pk>/versions/create/', views.version_create, name='version_create'),
    path('versions/<int:pk>/download/', views.version_download, name='version_download'),
    
    # ========================================================================
    # Sharing URLs
    # ========================================================================
    path('<int:pk>/share/', views.document_share, name='document_share'),
    path('shares/<int:pk>/revoke/', views.share_revoke, name='share_revoke'),
    
    # ========================================================================
    # Comment URLs
    # ========================================================================
    path('<int:document_pk>/comments/create/', views.comment_create, name='comment_create'),
    path('comments/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    
    # ========================================================================
    # Category URLs
    # ========================================================================
    path('categories/', views.category_list, name='category_list'),
    path('categories/<int:pk>/', views.category_documents, name='category_documents'),
    
    # ========================================================================
    # Bulk Actions URLs
    # ========================================================================
    path('bulk-actions/', views.bulk_actions, name='bulk_actions'),
]