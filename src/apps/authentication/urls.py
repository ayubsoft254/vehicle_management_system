"""
Authentication URL Configuration
All URL patterns for user management
"""
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Profile Management
    path('profile/', views.profile_view, name='profile'),
    
    # User Management - List & Search
    path('users/', views.user_list_view, name='user_list'),
    
    # User Management - CRUD Operations
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:pk>/', views.user_detail_view, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_update_view, name='user_update'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),
    
    # User Management - Status & Actions
    path('users/<int:pk>/toggle-status/', views.user_toggle_status_view, name='user_toggle_status'),
]