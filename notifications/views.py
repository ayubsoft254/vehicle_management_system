
from django.views.generic import ListView, DetailView, CreateView
from .models import Notification, NotificationTemplate
from django.urls import reverse_lazy

class NotificationListView(ListView):
	model = Notification
	template_name = 'notifications/notification_list.html'
	context_object_name = 'notifications'

class NotificationDetailView(DetailView):
	model = Notification
	template_name = 'notifications/notification_detail.html'
	context_object_name = 'notification'

class NotificationCreateView(CreateView):
	model = Notification
	fields = '__all__'
	template_name = 'notifications/notification_form.html'
	success_url = reverse_lazy('notifications:notification-list')

class NotificationTemplateListView(ListView):
	model = NotificationTemplate
	template_name = 'notifications/notificationtemplate_list.html'
	context_object_name = 'templates'

class NotificationTemplateDetailView(DetailView):
	model = NotificationTemplate
	template_name = 'notifications/notificationtemplate_detail.html'
	context_object_name = 'template'

class NotificationTemplateCreateView(CreateView):
	model = NotificationTemplate
	fields = '__all__'
	template_name = 'notifications/notificationtemplate_form.html'
	success_url = reverse_lazy('notifications:notificationtemplate-list')
