from django.urls import path
from .views import (
    DashboardView, ClientDashboardView, LandingPageView,
    UserListView, UserDetailView,
    CompanyListView, CompanyDetailView, contact
)

urlpatterns = [
    # Landing Page
    path('', LandingPageView.as_view(), name='landing'),

    # Staff/Admin Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # Client Dashboard
    path('client/dashboard/', ClientDashboardView.as_view(), name='client-dashboard'),

    # User Management
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),

    # Company Management
    path('companies/', CompanyListView.as_view(), name='company-list'),
    path('companies/<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),

    # Contact
    path('contact/', contact, name='contact'),
]
