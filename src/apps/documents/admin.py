"""
Admin configuration for the documents app.
Provides comprehensive document management interface in Django admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count
from .models import (
    Document, DocumentCategory, DocumentVersion, 
    DocumentShare, DocumentComment, DocumentTag
)


class DocumentVersionInline(admin.TabularInline):
    """Inline admin for document versions."""
    model = DocumentVersion
    extra = 0
    readonly_fields = ('version_number', 'uploaded_by', 'uploaded_at', 'file_size_display')
    fields = ('version_number', 'file', 'version_notes', 'uploaded_by', 'uploaded_at', 'file_size_display')
    
    def file_size_display(self, obj):
        """Display formatted file size."""
        if obj.file_size:
            return obj.get_file_size_display()
        return '-'
    file_size_display.short_description = 'File Size'
    
    def has_add_permission(self, request, obj=None):
        """Disable adding versions through inline."""
        return False


class DocumentShareInline(admin.TabularInline):
    """Inline admin for document shares."""
    model = DocumentShare
    extra = 0
    readonly_fields = ('shared_by', 'shared_at')
    fields = ('shared_with', 'shared_by', 'can_edit', 'can_delete', 'expires_at', 'shared_at')
    autocomplete_fields = ['shared_with']


class DocumentCommentInline(admin.TabularInline):
    """Inline admin for document comments."""
    model = DocumentComment
    extra = 0
    readonly_fields = ('user', 'created_at')
    fields = ('user', 'comment', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        """Disable adding comments through inline."""
        return False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin interface for documents."""
    
    list_display = (
        'title', 'category_link', 'file_type_badge', 'uploaded_by', 
        'file_size_display', 'download_count', 'is_public', 
        'is_archived', 'uploaded_at'
    )
    
    list_filter = (
        'is_public', 'is_archived', 'category', 'uploaded_at', 
        'file_type', 'expiry_date'
    )
    
    search_fields = (
        'title', 'description', 'uploaded_by__username', 
        'uploaded_by__email', 'tags__name'
    )
    
    readonly_fields = (
        'uploaded_by', 'uploaded_at', 'updated_at', 'file_size', 
        'file_type', 'file_name', 'download_count', 'archived_at',
        'preview_link'
    )
    
    autocomplete_fields = ['related_vehicle', 'related_client', 'tags']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title', 'description', 'category', 'tags'
            )
        }),
        ('File Information', {
            'fields': (
                'file', 'file_name', 'file_type', 'file_size', 'preview_link'
            )
        }),
        ('Relationships', {
            'fields': (
                'related_vehicle', 'related_client'
            ),
            'classes': ('collapse',)
        }),
        ('Access & Status', {
            'fields': (
                'is_public', 'is_archived', 'expiry_date'
            )
        }),
        ('Metadata', {
            'fields': (
                'uploaded_by', 'uploaded_at', 'updated_at', 
                'download_count', 'archived_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DocumentVersionInline, DocumentShareInline, DocumentCommentInline]
    
    date_hierarchy = 'uploaded_at'
    
    actions = [
        'make_public', 'make_private', 'archive_documents', 
        'unarchive_documents', 'reset_download_count'
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'uploaded_by', 'category', 'related_vehicle', 'related_client'
        ).prefetch_related('tags')
    
    def category_link(self, obj):
        """Display category as clickable link."""
        if obj.category:
            url = reverse('admin:documents_documentcategory_change', args=[obj.category.pk])
            return format_html('<a href="{}">{}</a>', url, obj.category.name)
        return '-'
    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'
    
    def file_type_badge(self, obj):
        """Display file type as colored badge."""
        color_map = {
            'pdf': '#dc3545',
            'doc': '#007bff',
            'docx': '#007bff',
            'xls': '#28a745',
            'xlsx': '#28a745',
            'jpg': '#fd7e14',
            'jpeg': '#fd7e14',
            'png': '#fd7e14',
            'txt': '#6c757d',
        }
        color = color_map.get(obj.file_type.lower(), '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.file_type.upper()
        )
    file_type_badge.short_description = 'Type'
    file_type_badge.admin_order_field = 'file_type'
    
    def file_size_display(self, obj):
        """Display formatted file size."""
        if obj.file_size:
            return obj.get_file_size_display()
        return '-'
    file_size_display.short_description = 'Size'
    file_size_display.admin_order_field = 'file_size'
    
    def preview_link(self, obj):
        """Display link to preview document."""
        if obj.pk:
            url = reverse('documents:document_preview', args=[obj.pk])
            return format_html('<a href="{}" target="_blank">Preview Document</a>', url)
        return '-'
    preview_link.short_description = 'Preview'
    
    def save_model(self, request, obj, form, change):
        """Set uploaded_by on creation."""
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    # Admin Actions
    @admin.action(description='Make selected documents public')
    def make_public(self, request, queryset):
        """Make documents public."""
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} document(s) made public.')
    
    @admin.action(description='Make selected documents private')
    def make_private(self, request, queryset):
        """Make documents private."""
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} document(s) made private.')
    
    @admin.action(description='Archive selected documents')
    def archive_documents(self, request, queryset):
        """Archive documents."""
        updated = queryset.update(is_archived=True, archived_at=timezone.now())
        self.message_user(request, f'{updated} document(s) archived.')
    
    @admin.action(description='Unarchive selected documents')
    def unarchive_documents(self, request, queryset):
        """Unarchive documents."""
        updated = queryset.update(is_archived=False, archived_at=None)
        self.message_user(request, f'{updated} document(s) unarchived.')
    
    @admin.action(description='Reset download count')
    def reset_download_count(self, request, queryset):
        """Reset download counters."""
        updated = queryset.update(download_count=0)
        self.message_user(request, f'Download count reset for {updated} document(s).')


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    """Admin interface for document categories."""
    
    list_display = (
        'name_with_icon', 'parent', 'document_count', 'color_display'
    )
    
    list_filter = ('parent',)
    
    search_fields = ('name', 'description')
    
    readonly_fields = ('document_count',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'parent')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color')
        }),
        ('Statistics', {
            'fields': ('document_count',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add document count annotation."""
        qs = super().get_queryset(request)
        return qs.annotate(doc_count=Count('documents'))
    
    def name_with_icon(self, obj):
        """Display name with icon."""
        if obj.icon:
            return format_html(
                '<i class="{}"></i> {}', 
                obj.icon, obj.name
            )
        return obj.name
    name_with_icon.short_description = 'Name'
    name_with_icon.admin_order_field = 'name'
    
    def document_count(self, obj):
        """Display count of documents in category."""
        return obj.doc_count if hasattr(obj, 'doc_count') else obj.documents.count()
    document_count.short_description = 'Documents'
    document_count.admin_order_field = 'doc_count'
    
    def color_display(self, obj):
        """Display color swatch."""
        if obj.color:
            return format_html(
                '<div style="width: 50px; height: 20px; background-color: {}; '
                'border: 1px solid #ccc; border-radius: 3px;"></div>',
                obj.color
            )
        return '-'
    color_display.short_description = 'Color'


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    """Admin interface for document versions."""
    
    list_display = (
        'document_link', 'version_number', 'uploaded_by', 
        'file_size_display', 'uploaded_at'
    )
    
    list_filter = ('uploaded_at',)
    
    search_fields = (
        'document__title', 'uploaded_by__username', 
        'version_notes'
    )
    
    readonly_fields = (
        'version_number', 'uploaded_by', 'uploaded_at', 
        'file_size', 'file_size_display'
    )
    
    fieldsets = (
        ('Version Information', {
            'fields': ('document', 'version_number', 'file', 'version_notes')
        }),
        ('Metadata', {
            'fields': (
                'uploaded_by', 'uploaded_at', 'file_size', 'file_size_display'
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'uploaded_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('document', 'uploaded_by')
    
    def document_link(self, obj):
        """Display document as clickable link."""
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    document_link.admin_order_field = 'document__title'
    
    def file_size_display(self, obj):
        """Display formatted file size."""
        if obj.file_size:
            return obj.get_file_size_display()
        return '-'
    file_size_display.short_description = 'Size'


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    """Admin interface for document shares."""
    
    list_display = (
        'document_link', 'shared_with', 'shared_by', 
        'permissions_display', 'shared_at', 'expires_at', 'is_expired'
    )
    
    list_filter = ('can_edit', 'can_delete', 'shared_at', 'expires_at')
    
    search_fields = (
        'document__title', 'shared_with__username', 
        'shared_by__username'
    )
    
    readonly_fields = ('shared_by', 'shared_at', 'is_expired')
    
    autocomplete_fields = ['document', 'shared_with']
    
    fieldsets = (
        ('Share Information', {
            'fields': ('document', 'shared_with', 'shared_by')
        }),
        ('Permissions', {
            'fields': ('can_edit', 'can_delete')
        }),
        ('Timing', {
            'fields': ('shared_at', 'expires_at', 'is_expired')
        }),
    )
    
    date_hierarchy = 'shared_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('document', 'shared_with', 'shared_by')
    
    def document_link(self, obj):
        """Display document as clickable link."""
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    document_link.admin_order_field = 'document__title'
    
    def permissions_display(self, obj):
        """Display permissions as badges."""
        badges = []
        if obj.can_edit:
            badges.append('<span style="background: #28a745; color: white; padding: 2px 6px; '
                         'border-radius: 3px; font-size: 10px;">EDIT</span>')
        if obj.can_delete:
            badges.append('<span style="background: #dc3545; color: white; padding: 2px 6px; '
                         'border-radius: 3px; font-size: 10px;">DELETE</span>')
        return format_html(' '.join(badges)) if badges else '-'
    permissions_display.short_description = 'Permissions'
    
    def is_expired(self, obj):
        """Check if share has expired."""
        if obj.expires_at and obj.expires_at < timezone.now():
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✗ Expired</span>'
            )
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">✓ Active</span>'
        )
    is_expired.short_description = 'Status'


@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    """Admin interface for document comments."""
    
    list_display = (
        'document_link', 'user', 'comment_preview', 'created_at'
    )
    
    list_filter = ('created_at',)
    
    search_fields = (
        'document__title', 'user__username', 'comment'
    )
    
    readonly_fields = ('user', 'created_at')
    
    fieldsets = (
        ('Comment Information', {
            'fields': ('document', 'user', 'comment')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('document', 'user')
    
    def document_link(self, obj):
        """Display document as clickable link."""
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    document_link.admin_order_field = 'document__title'
    
    def comment_preview(self, obj):
        """Display truncated comment."""
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comment'


@admin.register(DocumentTag)
class DocumentTagAdmin(admin.ModelAdmin):
    """Admin interface for document tags."""
    
    list_display = ('name', 'document_count', 'created_at')
    
    search_fields = ('name',)
    
    readonly_fields = ('created_at', 'document_count')
    
    fieldsets = (
        ('Tag Information', {
            'fields': ('name',)
        }),
        ('Statistics', {
            'fields': ('document_count', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add document count annotation."""
        qs = super().get_queryset(request)
        return qs.annotate(doc_count=Count('documents'))
    
    def document_count(self, obj):
        """Display count of documents with this tag."""
        return obj.doc_count if hasattr(obj, 'doc_count') else obj.documents.count()
    document_count.short_description = 'Documents'
    document_count.admin_order_field = 'doc_count'