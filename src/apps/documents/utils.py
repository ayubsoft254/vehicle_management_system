"""
Utility functions for the documents app.
Handles file operations, validation, processing, and document-related tasks.
"""

import os
import mimetypes
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.mail import send_mail


# ============================================================================
# File Handling Utilities
# ============================================================================

def generate_document_filename(instance, filename):
    """
    Generate a unique filename for uploaded documents.
    Format: documents/YYYY/MM/category/unique_filename.ext
    """
    ext = os.path.splitext(filename)[1].lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = hashlib.md5(f"{filename}{timestamp}".encode()).hexdigest()[:8]
    
    # Build path based on category and date
    year = datetime.now().year
    month = datetime.now().month
    category = instance.category.name.lower().replace(' ', '_') if instance.category else 'uncategorized'
    
    new_filename = f"{unique_id}_{timestamp}{ext}"
    return f"documents/{year}/{month:02d}/{category}/{new_filename}"


def generate_version_filename(instance, filename):
    """
    Generate filename for document versions.
    Format: documents/versions/document_id/v{version_number}_unique_filename.ext
    """
    ext = os.path.splitext(filename)[1].lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = hashlib.md5(f"{filename}{timestamp}".encode()).hexdigest()[:8]
    
    document_id = instance.document.id
    version_num = instance.version_number or 1
    
    new_filename = f"v{version_num}_{unique_id}_{timestamp}{ext}"
    return f"documents/versions/{document_id}/{new_filename}"


def get_file_size(file):
    """
    Get file size in bytes.
    """
    if hasattr(file, 'size'):
        return file.size
    elif hasattr(file, 'path') and os.path.exists(file.path):
        return os.path.getsize(file.path)
    return 0


def format_file_size(size_bytes):
    """
    Format file size in human-readable format.
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.2f} {size_names[i]}"


def get_file_type(filename):
    """
    Extract file extension/type from filename.
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext.replace('.', '') if ext else 'unknown'


def get_mime_type(filename):
    """
    Get MIME type for a file.
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'


def is_image_file(filename):
    """
    Check if file is an image based on extension.
    """
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    ext = os.path.splitext(filename)[1].lower()
    return ext in image_extensions


def is_document_file(filename):
    """
    Check if file is a document (text/office format).
    """
    doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.ods', '.odp']
    ext = os.path.splitext(filename)[1].lower()
    return ext in doc_extensions


def is_previewable_file(filename):
    """
    Check if file can be previewed in browser.
    """
    previewable_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt']
    ext = os.path.splitext(filename)[1].lower()
    return ext in previewable_extensions


# ============================================================================
# Image Processing Utilities
# ============================================================================

def generate_thumbnail(image_file, size=(300, 300)):
    """
    Generate thumbnail for an image file.
    Returns ContentFile with thumbnail data.
    """
    try:
        img = Image.open(image_file)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        thumb_io = BytesIO()
        img_format = img.format or 'JPEG'
        img.save(thumb_io, format=img_format, quality=85)
        thumb_io.seek(0)
        
        return ContentFile(thumb_io.read())
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def process_document_image(document):
    """
    Process image document to generate thumbnail.
    """
    if document.file and is_image_file(document.file.name):
        try:
            thumbnail = generate_thumbnail(document.file)
            if thumbnail:
                # Save thumbnail with same name but in thumbnails directory
                filename = os.path.basename(document.file.name)
                thumb_path = f"documents/thumbnails/{filename}"
                default_storage.save(thumb_path, thumbnail)
                return thumb_path
        except Exception as e:
            print(f"Error processing document image: {e}")
    return None


# ============================================================================
# File Validation Utilities
# ============================================================================

def validate_file_extension(filename, allowed_extensions=None):
    """
    Validate file extension against allowed list.
    """
    if allowed_extensions is None:
        allowed_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.csv', '.rtf', '.odt', '.ods', '.odp',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'
        ]
    
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_extensions


def validate_file_size(file, max_size_mb=50):
    """
    Validate file size against maximum allowed size.
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    file_size = get_file_size(file)
    return file_size <= max_size_bytes


def calculate_file_hash(file):
    """
    Calculate MD5 hash of file for duplicate detection.
    """
    hasher = hashlib.md5()
    
    if hasattr(file, 'read'):
        file.seek(0)
        for chunk in iter(lambda: file.read(4096), b""):
            hasher.update(chunk)
        file.seek(0)
    
    return hasher.hexdigest()


def check_duplicate_document(file, user=None):
    """
    Check if document with same hash already exists.
    Returns existing document if found, None otherwise.
    """
    from .models import Document
    
    file_hash = calculate_file_hash(file)
    
    query = Q(file_hash=file_hash)
    if user:
        query &= Q(uploaded_by=user)
    
    return Document.objects.filter(query).first()


# ============================================================================
# Document Search and Filtering Utilities
# ============================================================================

def search_documents(query, user=None, filters=None):
    """
    Search documents with advanced filtering.
    """
    from .models import Document
    
    # Base queryset
    documents = Document.objects.all()
    
    # Apply user access filter
    if user:
        documents = documents.filter(
            Q(uploaded_by=user) | Q(is_public=True) | Q(shared_with=user)
        ).distinct()
    
    # Apply search query
    if query:
        documents = documents.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()
    
    # Apply additional filters
    if filters:
        if 'category' in filters and filters['category']:
            documents = documents.filter(category=filters['category'])
        
        if 'file_type' in filters and filters['file_type']:
            documents = documents.filter(file_type=filters['file_type'])
        
        if 'date_from' in filters and filters['date_from']:
            documents = documents.filter(uploaded_at__gte=filters['date_from'])
        
        if 'date_to' in filters and filters['date_to']:
            documents = documents.filter(uploaded_at__lte=filters['date_to'])
        
        if 'is_archived' in filters:
            documents = documents.filter(is_archived=filters['is_archived'])
    
    return documents


def get_related_documents(document, limit=5):
    """
    Get documents related to a given document based on category, tags, and relationships.
    """
    from .models import Document
    
    related = Document.objects.exclude(pk=document.pk)
    
    # Filter by same category
    if document.category:
        related = related.filter(category=document.category)
    
    # Filter by shared tags
    if document.tags.exists():
        related = related.filter(tags__in=document.tags.all()).distinct()
    
    # Filter by same vehicle or client
    if document.related_vehicle:
        related = related.filter(related_vehicle=document.related_vehicle)
    elif document.related_client:
        related = related.filter(related_client=document.related_client)
    
    return related.order_by('-uploaded_at')[:limit]


# ============================================================================
# Document Expiry and Cleanup Utilities
# ============================================================================

def get_expired_documents():
    """
    Get all documents that have passed their expiry date.
    """
    from .models import Document
    
    return Document.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lt=timezone.now().date()
    )


def get_expired_shares():
    """
    Get all document shares that have expired.
    """
    from .models import DocumentShare
    
    return DocumentShare.objects.filter(
        expires_at__isnull=False,
        expires_at__lt=timezone.now()
    )


def cleanup_expired_shares():
    """
    Delete expired document shares.
    Returns count of deleted shares.
    """
    expired_shares = get_expired_shares()
    count = expired_shares.count()
    expired_shares.delete()
    return count


def archive_expired_documents():
    """
    Archive documents that have passed their expiry date.
    Returns count of archived documents.
    """
    expired_docs = get_expired_documents().filter(is_archived=False)
    count = expired_docs.update(
        is_archived=True,
        archived_at=timezone.now()
    )
    return count


def cleanup_orphaned_files():
    """
    Find and optionally delete files that don't have associated database records.
    """
    from .models import Document, DocumentVersion
    
    # Get all document files from database
    db_files = set()
    
    for doc in Document.objects.all():
        if doc.file:
            db_files.add(doc.file.name)
    
    for version in DocumentVersion.objects.all():
        if version.file:
            db_files.add(version.file.name)
    
    # Get all files from storage
    documents_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
    orphaned_files = []
    
    if os.path.exists(documents_dir):
        for root, dirs, files in os.walk(documents_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                
                if relative_path not in db_files:
                    orphaned_files.append(relative_path)
    
    return orphaned_files


# ============================================================================
# Document Statistics Utilities
# ============================================================================

def get_document_stats(user=None):
    """
    Get document statistics for dashboard.
    """
    from .models import Document, DocumentCategory
    from django.db.models import Count, Sum
    
    # Base queryset
    documents = Document.objects.all()
    if user:
        documents = documents.filter(uploaded_by=user)
    
    stats = {
        'total_documents': documents.count(),
        'active_documents': documents.filter(is_archived=False).count(),
        'archived_documents': documents.filter(is_archived=True).count(),
        'public_documents': documents.filter(is_public=True).count(),
        'total_downloads': documents.aggregate(Sum('download_count'))['download_count__sum'] or 0,
        'total_size': documents.aggregate(Sum('file_size'))['file_size__sum'] or 0,
    }
    
    # Documents by category
    stats['by_category'] = list(
        documents.values('category__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # Documents by file type
    stats['by_file_type'] = list(
        documents.values('file_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Recent uploads
    stats['recent_uploads'] = documents.order_by('-uploaded_at')[:10]
    
    return stats


def get_user_storage_usage(user):
    """
    Calculate total storage used by a user's documents.
    """
    from .models import Document
    from django.db.models import Sum
    
    total_size = Document.objects.filter(
        uploaded_by=user
    ).aggregate(Sum('file_size'))['file_size__sum'] or 0
    
    return {
        'total_bytes': total_size,
        'total_formatted': format_file_size(total_size),
        'document_count': Document.objects.filter(uploaded_by=user).count(),
    }


def get_popular_documents(limit=10, days=30):
    """
    Get most downloaded documents within specified time period.
    """
    from .models import Document
    
    since_date = timezone.now() - timedelta(days=days)
    
    return Document.objects.filter(
        uploaded_at__gte=since_date
    ).order_by('-download_count')[:limit]


# ============================================================================
# Document Notification Utilities
# ============================================================================

def notify_document_shared(share):
    """
    Send notification when document is shared.
    """
    # TODO: Integrate with notifications app
    from django.core.mail import send_mail
    
    subject = f"Document shared with you: {share.document.title}"
    message = f"""
    {share.shared_by.get_full_name() or share.shared_by.username} has shared a document with you.
    
    Document: {share.document.title}
    Permissions: {'Can Edit' if share.can_edit else 'View Only'}
    {f'Expires: {share.expires_at}' if share.expires_at else ''}
    
    View the document in your dashboard.
    """
    
    recipient = share.shared_with.email
    if recipient:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=True,
        )


def notify_document_comment(comment):
    """
    Send notification when document receives a comment.
    """
    # TODO: Integrate with notifications app
    from django.core.mail import send_mail
    
    document = comment.document
    
    # Notify document owner
    if document.uploaded_by.email and document.uploaded_by != comment.user:
        subject = f"New comment on your document: {document.title}"
        message = f"""
        {comment.user.get_full_name() or comment.user.username} commented on your document.
        
        Document: {document.title}
        Comment: {comment.comment}
        
        View the document in your dashboard.
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [document.uploaded_by.email],
            fail_silently=True,
        )


def notify_document_expiring(days_before=7):
    """
    Send notifications for documents expiring soon.
    Returns count of notifications sent.
    """
    from .models import Document
    
    expiry_date = timezone.now().date() + timedelta(days=days_before)
    
    expiring_docs = Document.objects.filter(
        expiry_date=expiry_date,
        is_archived=False
    ).select_related('uploaded_by')
    
    count = 0
    for doc in expiring_docs:
        if doc.uploaded_by.email:
            subject = f"Document expiring soon: {doc.title}"
            message = f"""
            Your document "{doc.title}" will expire on {doc.expiry_date}.
            
            Please review and take necessary action.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [doc.uploaded_by.email],
                fail_silently=True,
            )
            count += 1
    
    return count


# ============================================================================
# Export and Backup Utilities
# ============================================================================

def export_document_metadata(documents, format='csv'):
    """
    Export document metadata to CSV or JSON.
    """
    import csv
    import json
    from io import StringIO
    
    if format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'ID', 'Title', 'Category', 'File Type', 'File Size',
            'Uploaded By', 'Uploaded At', 'Downloads', 'Is Public', 'Is Archived'
        ])
        
        # Data
        for doc in documents:
            writer.writerow([
                doc.id,
                doc.title,
                doc.category.name if doc.category else '',
                doc.file_type,
                doc.get_file_size_display(),
                doc.uploaded_by.username,
                doc.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
                doc.download_count,
                doc.is_public,
                doc.is_archived,
            ])
        
        return output.getvalue()
    
    elif format == 'json':
        data = []
        for doc in documents:
            data.append({
                'id': doc.id,
                'title': doc.title,
                'category': doc.category.name if doc.category else None,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'uploaded_by': doc.uploaded_by.username,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'download_count': doc.download_count,
                'is_public': doc.is_public,
                'is_archived': doc.is_archived,
            })
        
        return json.dumps(data, indent=2)