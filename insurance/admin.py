
from django.contrib import admin
from .models import InsuranceProvider, Insurance

@admin.register(InsuranceProvider)
class InsuranceProviderAdmin(admin.ModelAdmin):
	list_display = ("name", "phone", "email", "is_active", "created_at")
	search_fields = ("name", "email")
	list_filter = ("is_active",)

@admin.register(Insurance)
class InsuranceAdmin(admin.ModelAdmin):
	list_display = ("vehicle", "client", "provider", "policy_number", "insurance_type", "status", "start_date", "end_date")
	search_fields = ("policy_number", "provider__name", "vehicle__vin")
	list_filter = ("insurance_type", "status", "provider")
