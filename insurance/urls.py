
from django.urls import path
from . import views

app_name = 'insurance'

urlpatterns = [
	path('', views.InsuranceListView.as_view(), name='insurance-list'),
	path('create/', views.InsuranceCreateView.as_view(), name='insurance-create'),
	path('<int:pk>/', views.InsuranceDetailView.as_view(), name='insurance-detail'),

	path('providers/', views.InsuranceProviderListView.as_view(), name='insuranceprovider-list'),
	path('providers/create/', views.InsuranceProviderCreateView.as_view(), name='insuranceprovider-create'),
	path('providers/<int:pk>/', views.InsuranceProviderDetailView.as_view(), name='insuranceprovider-detail'),
]
