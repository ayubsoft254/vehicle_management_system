
from django.contrib import admin
from .models import NotificationTemplate, Notification

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
	list_display = ("name", "notification_type", "delivery_method", "is_active", "auto_send", "created_at")
	search_fields = ("name", "notification_type")
	list_filter = ("notification_type", "is_active", "delivery_method")

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ("template", "recipient", "delivery_method", "status", "scheduled_at", "sent_at")
	search_fields = ("recipient__first_name", "recipient__last_name", "recipient__company_name")
	list_filter = ("status", "delivery_method", "template")
