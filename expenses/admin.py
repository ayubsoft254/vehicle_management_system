
from django.contrib import admin
from .models import ExpenseCategory, Expense

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "is_active", "created_at")
	search_fields = ("name",)
	list_filter = ("is_active",)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "expense_type", "amount", "status", "expense_date", "recorded_by")
	search_fields = ("title", "vendor_name", "receipt_number", "invoice_number")
	list_filter = ("expense_type", "status", "category")
