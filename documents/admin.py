
from django.contrib import admin
from .models import DocumentCategory, Document

@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "is_active", "created_at")
	search_fields = ("name",)
	list_filter = ("is_active",)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
	list_display = ("title", "document_type", "category", "client", "vehicle", "is_active", "uploaded_by", "created_at")
	search_fields = ("title", "description", "document_type")
	list_filter = ("document_type", "is_active", "category")
