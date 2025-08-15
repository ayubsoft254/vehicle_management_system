
from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
	list_display = ("full_name", "client_type", "email", "phone", "is_active", "is_blacklisted", "created_at")
	search_fields = ("first_name", "last_name", "company_name", "email", "id_number")
	list_filter = ("client_type", "is_active", "is_blacklisted")
