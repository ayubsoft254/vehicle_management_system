# urls for core app views
from django.urls import path
from .views import (
	DashboardView, LandingPageView,
	UserListView, UserDetailView,
	CompanyListView, CompanyDetailView,
)

urlpatterns = [
	path('', LandingPageView.as_view(), name='landing'),
	path('dashboard/', DashboardView.as_view(), name='dashboard'),
	path('users/', UserListView.as_view(), name='user-list'),
	path('users/<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
	path('companies/', CompanyListView.as_view(), name='company-list'),
	path('companies/<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),
]
