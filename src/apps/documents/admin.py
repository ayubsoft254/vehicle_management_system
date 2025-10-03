"""
Admin configuration for the documents app.
Simplified version with only existing models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Document, DocumentCategory, 
    DocumentShare, DocumentAccess, DocumentPermission
)


class DocumentShareInline(admin.TabularInline):
    """Inline admin for document shares."""
    model = DocumentShare
    extra = 0
    readonly_fields = ('shared_by', 'shared_at')
    fields = ('shared_with', 'shared_by', 'can_edit', 'can_delete', 'expires_at', 'shared_at')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin interface for documents."""
    
    list_display = ('title', 'category', 'uploaded_by', 'uploaded_at')
    list_filter = ('category', 'uploaded_at')
    search_fields = ('title', 'description')
    readonly_fields = ('uploaded_by', 'uploaded_at', 'updated_at')
    inlines = [DocumentShareInline]
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking."""
        if not change:  # New object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    """Admin interface for document categories."""
    
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    """Admin interface for document shares."""
    
    list_display = ('document', 'shared_with', 'shared_by', 'can_edit', 'can_delete', 'shared_at')
    list_filter = ('can_edit', 'can_delete', 'shared_at')
    readonly_fields = ('shared_by', 'shared_at')
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking."""
        if not change:  # New object
            obj.shared_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DocumentAccess)
class DocumentAccessAdmin(admin.ModelAdmin):
    """Admin interface for document access."""
    
    list_display = ('document', 'user', 'access_type', 'accessed_at')
    list_filter = ('access_type', 'accessed_at')
    readonly_fields = ('accessed_at',)


@admin.register(DocumentPermission)
class DocumentPermissionAdmin(admin.ModelAdmin):
    """Admin interface for document permissions."""
    
    list_display = ('document', 'user', 'permission_type', 'granted_at')
    list_filter = ('permission_type', 'granted_at')
    readonly_fields = ('granted_at',)