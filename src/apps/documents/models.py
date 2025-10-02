"""
Models for the documents app
Handles document storage, categorization, versioning, and access control
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os
from datetime import date

User = get_user_model()


# ==================== CUSTOM MANAGERS ====================

class DocumentManager(models.Manager):
    """Custom manager for Document model"""
    
    def active(self):
        """Get active documents"""
        return self.filter(is_active=True)
    
    def by_category(self, category):
        """Get documents by category"""
        return self.filter(category=category)
    
    def by_owner(self, user):
        """Get documents uploaded by a user"""
        return self.filter(uploaded_by=user)
    
    def recent(self, days=7):
        """Get recently uploaded documents"""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(uploaded_at__gte=cutoff_date)
    
    def expiring_soon(self, days=30):
        """Get documents expiring within specified days"""
        from datetime import timedelta
        today = timezone.now().date()
        future_date = today + timedelta(days=days)
        return self.filter(
            expiry_date__isnull=False,
            expiry_date__range=[today, future_date]
        )


# ==================== DOCUMENT CATEGORY MODEL ====================

class DocumentCategory(models.Model):
    """
    Model for document categories
    """
    
    # Category Details
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name"
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly identifier"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Category description"
    )
    
    # Category Icon/Color
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Icon class (e.g., 'fa-file', 'fa-folder')"
    )
    
    color = models.CharField(
        max_length=7,
        default='#007bff',
        help_text="Hex color code for UI"
    )
    
    # Settings
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is active"
    )
    
    require_expiry_date = models.BooleanField(
        default=False,
        help_text="Whether documents in this category require expiry dates"
    )
    
    allowed_file_types = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Comma-separated allowed file extensions (e.g., 'pdf,doc,docx')"
    )
    
    max_file_size_mb = models.PositiveIntegerField(
        default=10,
        help_text="Maximum file size in MB"
    )
    
    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Document Category'
        verbose_name_plural = 'Document Categories'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def document_count(self):
        """Get count of documents in this category"""
        return self.documents.filter(is_active=True).count()
    
    def get_allowed_extensions(self):
        """Get list of allowed file extensions"""
        if self.allowed_file_types:
            return [ext.strip() for ext in self.allowed_file_types.split(',')]
        return []


# ==================== DOCUMENT MODEL ====================

def document_upload_path(instance, filename):
    """
    Generate upload path for documents
    Format: documents/{category}/{year}/{month}/{filename}
    """
    now = timezone.now()
    category_slug = instance.category.slug if instance.category else 'uncategorized'
    return f'documents/{category_slug}/{now.year}/{now.month:02d}/{filename}'


class Document(models.Model):
    """
    Model for document storage with versioning and access control
    """
    
    # Document Details
    title = models.CharField(
        max_length=255,
        help_text="Document title"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Document description"
    )
    
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name='documents',
        help_text="Document category"
    )
    
    # File Information
    file = models.FileField(
        upload_to=document_upload_path,
        help_text="Document file"
    )
    
    file_size = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="File size in bytes"
    )
    
    file_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="File MIME type"
    )
    
    # Generic Foreign Key for linking to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text="Type of related object"
    )
    object_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="ID of related object"
    )
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Alternative: Direct Foreign Keys (uncomment if needed)
    # client = models.ForeignKey(
    #     'clients.Client',
    #     on_delete=models.CASCADE,
    #     blank=True,
    #     null=True,
    #     related_name='documents'
    # )
    # vehicle = models.ForeignKey(
    #     'vehicles.Vehicle',
    #     on_delete=models.CASCADE,
    #     blank=True,
    #     null=True,
    #     related_name='documents'
    # )
    
    # Document Metadata
    document_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Document reference number (e.g., contract number)"
    )
    
    issue_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date document was issued"
    )
    
    expiry_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date document expires"
    )
    
    # Version Control
    version = models.PositiveIntegerField(
        default=1,
        help_text="Document version number"
    )
    
    is_latest_version = models.BooleanField(
        default=True,
        help_text="Whether this is the latest version"
    )
    
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='next_versions',
        help_text="Previous version of this document"
    )
    
    # Access Control
    is_private = models.BooleanField(
        default=False,
        help_text="Whether this document is private"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this document is active"
    )
    
    # Tags for better search
    tags = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Comma-separated tags for search"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes"
    )
    
    # System Fields
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        help_text="User who uploaded this document"
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Download Tracking
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times downloaded"
    )
    
    last_downloaded_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last download timestamp"
    )
    
    # Custom Manager
    objects = DocumentManager()
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['category', 'uploaded_at']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['is_active', 'is_latest_version']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.title} (v{self.version})"
    
    def save(self, *args, **kwargs):
        """Auto-populate file metadata"""
        if self.file:
            # Set file size
            if not self.file_size:
                self.file_size = self.file.size
            
            # Set file type
            if not self.file_type:
                self.file_type = self.get_file_extension()
        
        super().save(*args, **kwargs)
    
    def get_file_extension(self):
        """Get file extension"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ''
    
    @property
    def file_size_formatted(self):
        """Get human-readable file size"""
        if not self.file_size:
            return 'Unknown'
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    @property
    def is_expired(self):
        """Check if document has expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        if self.expiry_date:
            today = timezone.now().date()
            if self.expiry_date >= today:
                delta = self.expiry_date - today
                return delta.days
        return None
    
    @property
    def is_expiring_soon(self, days=30):
        """Check if document is expiring within specified days"""
        days_left = self.days_until_expiry
        if days_left is not None:
            return 0 < days_left <= days
        return False
    
    @property
    def is_image(self):
        """Check if document is an image"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']
        return self.get_file_extension() in image_extensions
    
    @property
    def is_pdf(self):
        """Check if document is a PDF"""
        return self.get_file_extension() == '.pdf'
    
    @property
    def is_document(self):
        """Check if document is a text document"""
        doc_extensions = ['.doc', '.docx', '.txt', '.rtf', '.odt']
        return self.get_file_extension() in doc_extensions
    
    @property
    def is_spreadsheet(self):
        """Check if document is a spreadsheet"""
        sheet_extensions = ['.xls', '.xlsx', '.csv', '.ods']
        return self.get_file_extension() in sheet_extensions
    
    def get_tags_list(self):
        """Get list of tags"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.save(update_fields=['download_count', 'last_downloaded_at'])
    
    def create_new_version(self, new_file, uploaded_by, notes=''):
        """
        Create a new version of this document
        
        Args:
            new_file: New file upload
            uploaded_by: User uploading new version
            notes: Version notes
        
        Returns:
            Document: New version instance
        """
        # Mark current version as not latest
        self.is_latest_version = False
        self.save(update_fields=['is_latest_version'])
        
        # Create new version
        new_version = Document.objects.create(
            title=self.title,
            description=self.description,
            category=self.category,
            file=new_file,
            content_type=self.content_type,
            object_id=self.object_id,
            document_number=self.document_number,
            issue_date=self.issue_date,
            expiry_date=self.expiry_date,
            version=self.version + 1,
            is_latest_version=True,
            previous_version=self,
            is_private=self.is_private,
            tags=self.tags,
            notes=notes,
            uploaded_by=uploaded_by
        )
        
        return new_version
    
    def get_version_history(self):
        """Get all versions of this document"""
        versions = []
        current = self
        
        # Get all previous versions
        while current.previous_version:
            versions.append(current.previous_version)
            current = current.previous_version
        
        # Get all next versions
        current = self
        next_versions = list(current.next_versions.all())
        
        # Combine and sort
        all_versions = versions + [self] + next_versions
        return sorted(all_versions, key=lambda v: v.version, reverse=True)


# ==================== DOCUMENT ACCESS MODEL ====================

class DocumentAccess(models.Model):
    """
    Model for tracking document access permissions and history
    """
    
    ACCESS_TYPE_CHOICES = [
        ('view', 'View Only'),
        ('download', 'Download'),
        ('edit', 'Edit'),
        ('delete', 'Delete'),
    ]
    
    # Document & User
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='access_logs',
        help_text="Document accessed"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='document_accesses',
        help_text="User who accessed"
    )
    
    # Access Details
    access_type = models.CharField(
        max_length=20,
        choices=ACCESS_TYPE_CHOICES,
        help_text="Type of access"
    )
    
    accessed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When access occurred"
    )
    
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        help_text="IP address of accessor"
    )
    
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Browser/device user agent"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Access notes"
    )
    
    class Meta:
        ordering = ['-accessed_at']
        verbose_name = 'Document Access Log'
        verbose_name_plural = 'Document Access Logs'
        indexes = [
            models.Index(fields=['document', 'accessed_at']),
            models.Index(fields=['user', 'accessed_at']),
            models.Index(fields=['access_type']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_access_type_display()} - {self.document.title}"


# ==================== DOCUMENT PERMISSION MODEL ====================

class DocumentPermission(models.Model):
    """
    Model for document-level permissions
    """
    
    PERMISSION_CHOICES = [
        ('view', 'Can View'),
        ('download', 'Can Download'),
        ('edit', 'Can Edit'),
        ('delete', 'Can Delete'),
        ('manage', 'Can Manage Permissions'),
    ]
    
    # Document & User
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='permissions',
        help_text="Document"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='document_permissions',
        help_text="User with permission"
    )
    
    # Permission
    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        help_text="Permission type"
    )
    
    # Validity
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When permission expires"
    )
    
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_document_permissions',
        help_text="Who granted this permission"
    )
    
    class Meta:
        ordering = ['-granted_at']
        verbose_name = 'Document Permission'
        verbose_name_plural = 'Document Permissions'
        unique_together = ['document', 'user', 'permission']
        indexes = [
            models.Index(fields=['document', 'user']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_permission_display()} - {self.document.title}"
    
    @property
    def is_expired(self):
        """Check if permission has expired"""
        if self.expires_at:
            return self.expires_at < timezone.now()
        return False
    
    @property
    def is_active(self):
        """Check if permission is currently active"""
        return not self.is_expired


# ==================== DOCUMENT SHARING MODEL ====================

class DocumentShare(models.Model):
    """
    Model for sharing documents via links
    """
    
    # Document
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='shares',
        help_text="Document being shared"
    )
    
    # Share Details
    share_token = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique share token"
    )
    
    password = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Optional password protection"
    )
    
    # Settings
    allow_download = models.BooleanField(
        default=True,
        help_text="Whether download is allowed"
    )
    
    max_downloads = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Maximum number of downloads allowed"
    )
    
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Current download count"
    )
    
    # Validity
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When share link expires"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_shares',
        help_text="User who created share"
    )
    
    # Tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Whether share is active"
    )
    
    last_accessed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last access timestamp"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document Share'
        verbose_name_plural = 'Document Shares'
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['document']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Share: {self.document.title} - {self.share_token[:8]}..."
    
    @property
    def is_expired(self):
        """Check if share has expired"""
        if self.expires_at:
            return self.expires_at < timezone.now()
        return False
    
    @property
    def is_valid(self):
        """Check if share is valid"""
        if not self.is_active:
            return False
        if self.is_expired:
            return False
        if self.max_downloads and self.download_count >= self.max_downloads:
            return False
        return True
    
    def increment_download(self):
        """Increment download counter"""
        self.download_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed_at'])


# ==================== SIGNAL HANDLERS ====================

@receiver(post_delete, sender=Document)
def delete_document_file(sender, instance, **kwargs):
    """
    Delete file from filesystem when document is deleted
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)