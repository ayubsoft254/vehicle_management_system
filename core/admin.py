
from django.contrib import admin
from .models import User, RolePermission, Company, MiscellaneousFinancial, WarrantyTracking

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("username", "email", "role", "is_active_employee", "department", "hire_date")
	search_fields = ("username", "email", "role", "employee_id")
	list_filter = ("role", "is_active_employee", "department")

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
	list_display = ("role", "module_name", "access_level", "created_at")
	list_filter = ("role", "module_name", "access_level")
	search_fields = ("role", "module_name")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
	list_display = ("name", "registration_number", "email", "phone", "is_active", "created_at")
	search_fields = ("name", "registration_number", "email")
	list_filter = ("is_active",)

@admin.register(MiscellaneousFinancial)
class MiscellaneousFinancialAdmin(admin.ModelAdmin):
	list_display = ("title", "financial_type", "amount", "status", "transaction_date", "client", "vehicle")
	search_fields = ("title", "reference_number", "description")
	list_filter = ("financial_type", "status", "transaction_date")

@admin.register(WarrantyTracking)
class WarrantyTrackingAdmin(admin.ModelAdmin):
	list_display = ("vehicle", "warranty_type", "warranty_provider", "status", "start_date", "end_date")
	search_fields = ("warranty_number", "warranty_provider")
	list_filter = ("warranty_type", "status", "start_date", "end_date")
