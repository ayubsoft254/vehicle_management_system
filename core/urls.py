from django.urls import path, include
from .views import (
    DashboardView, LandingPageView,
    UserListView, UserDetailView,
    CompanyListView, CompanyDetailView,
)

urlpatterns = [
    # Landing Page
    path('', LandingPageView.as_view(), name='landing'),

    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # User Management
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),

    # Company Management
    path('companies/', CompanyListView.as_view(), name='company-list'),
    path('companies/<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),
]
