
from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
	path('', views.DocumentListView.as_view(), name='document-list'),
	path('create/', views.DocumentCreateView.as_view(), name='document-create'),
	path('<int:pk>/', views.DocumentDetailView.as_view(), name='document-detail'),

	path('categories/', views.DocumentCategoryListView.as_view(), name='documentcategory-list'),
	path('categories/create/', views.DocumentCategoryCreateView.as_view(), name='documentcategory-create'),
	path('categories/<int:pk>/', views.DocumentCategoryDetailView.as_view(), name='documentcategory-detail'),
]
