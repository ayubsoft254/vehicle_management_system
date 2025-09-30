from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Home and Dashboard
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # User Profile
    path('profile/', views.profile_view, name='profile'),
    
    # User Management (Admin only)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    
    # System Settings
    path('settings/', views.settings_view, name='settings'),
]