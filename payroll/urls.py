
from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
	# Payroll URLs
	path('', views.PayrollListView.as_view(), name='payroll-list'),
	path('create/', views.PayrollCreateView.as_view(), name='payroll-create'),
	path('<int:pk>/', views.PayrollDetailView.as_view(), name='payroll-detail'),
	path('<int:pk>/update/', views.PayrollUpdateView.as_view(), name='payroll-update'),
	path('<int:pk>/delete/', views.PayrollDeleteView.as_view(), name='payroll-delete'),

	# Employee Loan URLs
	path('loans/', views.EmployeeLoanListView.as_view(), name='employeeloan-list'),
	path('loans/create/', views.EmployeeLoanCreateView.as_view(), name='employeeloan-create'),
	path('loans/<int:pk>/', views.EmployeeLoanDetailView.as_view(), name='employeeloan-detail'),
	path('loans/<int:pk>/update/', views.EmployeeLoanUpdateView.as_view(), name='employeeloan-update'),
	path('loans/<int:pk>/delete/', views.EmployeeLoanDeleteView.as_view(), name='employeeloan-delete'),
]
