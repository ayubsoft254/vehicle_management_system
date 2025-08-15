
from django.contrib import admin
from .models import ReportTemplate, ReportGeneration

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
	list_display = ("name", "report_type", "default_format", "is_active", "created_by", "created_at")
	search_fields = ("name", "report_type")
	list_filter = ("report_type", "is_active")

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
	list_display = ("template", "output_format", "status", "generated_by", "created_at")
	search_fields = ("template__name", "status")
	list_filter = ("status", "output_format")
