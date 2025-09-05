from django.urls import path
from . import views

app_name = 'clients'

from . import views

urlpatterns = [
	path('', views.ClientListView.as_view(), name='client-list'),
	path('create/', views.ClientCreateView.as_view(), name='client-create'),
	path('<int:pk>/', views.ClientDetailView.as_view(), name='client-detail'),
]