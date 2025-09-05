
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
	path('', views.NotificationListView.as_view(), name='notification-list'),
	path('create/', views.NotificationCreateView.as_view(), name='notification-create'),
	path('<int:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),

	path('templates/', views.NotificationTemplateListView.as_view(), name='notificationtemplate-list'),
	path('templates/create/', views.NotificationTemplateCreateView.as_view(), name='notificationtemplate-create'),
	path('templates/<int:pk>/', views.NotificationTemplateDetailView.as_view(), name='notificationtemplate-detail'),
]
