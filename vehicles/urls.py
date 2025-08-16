from django.urls import path
from .views import (
	VehicleListView, VehicleDetailView, VehicleCreateView, VehicleUpdateView, VehicleDeleteView,
	add_vehicle_image, delete_vehicle_image, add_vehicle_expense, delete_vehicle_expense
)

urlpatterns = [
	path('', VehicleListView.as_view(), name='vehicle-list'),
	path('add/', VehicleCreateView.as_view(), name='vehicle-add'),
	path('<uuid:pk>/', VehicleDetailView.as_view(), name='vehicle-detail'),
	path('<uuid:pk>/edit/', VehicleUpdateView.as_view(), name='vehicle-edit'),
	path('<uuid:pk>/delete/', VehicleDeleteView.as_view(), name='vehicle-delete'),

	# Vehicle images
	path('<uuid:pk>/images/add/', add_vehicle_image, name='vehicleimage-add'),
	path('images/<int:image_id>/delete/', delete_vehicle_image, name='vehicleimage-delete'),

	# Vehicle expenses
	path('<uuid:pk>/expenses/add/', add_vehicle_expense, name='vehicleexpense-add'),
	path('expenses/<int:expense_id>/delete/', delete_vehicle_expense, name='vehicleexpense-delete'),
]
