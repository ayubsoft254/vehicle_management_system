
from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
	path('', views.ExpenseListView.as_view(), name='expense-list'),
	path('create/', views.ExpenseCreateView.as_view(), name='expense-create'),
	path('<int:pk>/', views.ExpenseDetailView.as_view(), name='expense-detail'),

	path('categories/', views.ExpenseCategoryListView.as_view(), name='expensecategory-list'),
	path('categories/create/', views.ExpenseCategoryCreateView.as_view(), name='expensecategory-create'),
	path('categories/<int:pk>/', views.ExpenseCategoryDetailView.as_view(), name='expensecategory-detail'),
]
