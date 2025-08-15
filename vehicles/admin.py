
from django.contrib import admin
from .models import Vehicle, VehicleImage, VehicleExpense

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
	list_display = ("make", "model", "year", "vin", "company", "status", "purchase_price", "selling_price", "created_at")
	search_fields = ("make", "model", "vin", "license_plate")
	list_filter = ("status", "company", "year", "make")

@admin.register(VehicleImage)
class VehicleImageAdmin(admin.ModelAdmin):
	list_display = ("vehicle", "caption", "is_primary", "uploaded_at")
	search_fields = ("vehicle__vin", "caption")
	list_filter = ("is_primary",)

@admin.register(VehicleExpense)
class VehicleExpenseAdmin(admin.ModelAdmin):
	list_display = ("vehicle", "category", "amount", "expense_date", "recorded_by")
	search_fields = ("vehicle__vin", "description", "vendor")
	list_filter = ("category",)
