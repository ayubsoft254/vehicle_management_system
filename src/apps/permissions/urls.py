"""
Permissions URL Configuration
"""
from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # Permission List & Search
    path('', views.permission_list_view, name='list'),
    
    # Permission CRUD Operations
    path('create/', views.permission_create_view, name='create'),
    path('<int:pk>/', views.permission_detail_view, name='detail'),
    path('<int:pk>/edit/', views.permission_update_view, name='update'),
    path('<int:pk>/delete/', views.permission_delete_view, name='delete'),
    
    # Permission Actions
    path('<int:pk>/toggle-status/', views.permission_toggle_status_view, name='toggle_status'),
    path('<int:pk>/history/', views.permission_history_view, name='history'),
    
    # Bulk Operations
    path('bulk-update/', views.bulk_permission_update_view, name='bulk_update'),
    
    # Role Matrix View
    path('role-matrix/', views.role_matrix_view, name='role_matrix_select'),
    path('role-matrix/<str:role>/', views.role_matrix_view, name='role_matrix'),
    
    # System Setup
    path('initialize/', views.initialize_permissions_view, name='initialize'),
]