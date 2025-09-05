
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
	path('', views.PaymentListView.as_view(), name='payment-list'),
	path('create/', views.PaymentCreateView.as_view(), name='payment-create'),
	path('<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),

	path('installmentplans/', views.InstallmentPlanListView.as_view(), name='installmentplan-list'),
	path('installmentplans/create/', views.InstallmentPlanCreateView.as_view(), name='installmentplan-create'),
	path('installmentplans/<int:pk>/', views.InstallmentPlanDetailView.as_view(), name='installmentplan-detail'),
]
