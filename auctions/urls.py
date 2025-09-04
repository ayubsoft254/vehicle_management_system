from django.urls import path
from . import views

urlpatterns = [
	path('', views.AuctionListView.as_view(), name='auction-list'),
	path('create/', views.AuctionCreateView.as_view(), name='auction-create'),
	path('<uuid:pk>/', views.AuctionDetailView.as_view(), name='auction-detail'),

	path('<uuid:auction_id>/vehicles/', views.AuctionVehicleListView.as_view(), name='auctionvehicle-list'),
	path('vehicles/create/', views.AuctionVehicleCreateView.as_view(), name='auctionvehicle-create'),
	path('vehicles/<uuid:pk>/', views.AuctionVehicleDetailView.as_view(), name='auctionvehicle-detail'),
]
from django.shortcuts import render
