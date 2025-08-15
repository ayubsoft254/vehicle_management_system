
from django.contrib import admin
from .models import InstallmentPlan, Payment

@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
	list_display = ("client", "vehicle", "total_amount", "deposit_amount", "monthly_payment", "status", "start_date", "end_date")
	search_fields = ("client__first_name", "client__last_name", "vehicle__vin")
	list_filter = ("status",)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("installment_plan", "amount", "payment_type", "payment_method", "status", "payment_date", "due_date")
	search_fields = ("installment_plan__client__first_name", "installment_plan__client__last_name", "transaction_id")
	list_filter = ("payment_type", "status", "payment_method")
