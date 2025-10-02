"""
Signal handlers for the documents app.
Handles automatic processing, notifications, and cleanup tasks.
"""

from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.files.storage import default_storage
from django.utils import timezone
import os

from .models import (
    Document, DocumentVersion, DocumentShare, 
    DocumentComment, DocumentTag
)
from .utils import (
    get_file_size, get_file_type, calculate_file_hash,
    process_document_image, notify_document_shared,
    notify_document_comment
)


# ============================================================================
# Document Signals
# ============================================================================

@receiver(pre_save, sender=Document)
def document_pre_save(sender, instance, **kwargs):
    """
    Process document before saving.
    - Extract file metadata
    - Calculate file hash
    - Handle file replacement
    """
    if instance.file:
        # Extract file metadata
        if not instance.file_name:
            instance.file_name = os.path.basename(instance.file.name)
        
        if not instance.file_size:
            instance.file_size = get_file_size(instance.file)
        
        if not instance.file_type:
            instance.file_type = get_file_type(instance.file.name)
        
        # Calculate file hash for duplicate detection
        if not instance.file_hash:
            try:
                instance.file_hash = calculate_file_hash(instance.file)
            except Exception as e:
                print(f"Error calculating file hash: {e}")
        
        # If this is an update and file changed, delete old file
        if instance.pk:
            try:
                old_instance = Document.objects.get(pk=instance.pk)
                if old_instance.file and old_instance.file != instance.file:
                    # Delete old file
                    if default_storage.exists(old_instance.file.name):
                        default_storage.delete(old_instance.file.name)
            except Document.DoesNotExist:
                pass


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    Process document after saving.
    - Generate thumbnails for images
    - Create initial version record
    - Send notifications
    """
    if created:
        # Generate thumbnail for images
        if instance.file:
            try:
                thumbnail_path = process_document_image(instance)
                if thumbnail_path:
                    # Update instance with thumbnail path if you add that field
                    pass
            except Exception as e:
                print(f"Error processing document image: {e}")
        
        # Create initial version record
        try:
            DocumentVersion.objects.create(
                document=instance,
                file=instance.file,
                version_number=1,
                uploaded_by=instance.uploaded_by,
                version_notes="Initial version"
            )
        except Exception as e:
            print(f"Error creating initial version: {e}")
        
        # Log document creation
        print(f"Document created: {instance.title} by {instance.uploaded_by}")


@receiver(post_delete, sender=Document)
def document_post_delete(sender, instance, **kwargs):
    """
    Cleanup after document deletion.
    - Delete associated file
    - Delete thumbnail if exists
    """
    # Delete the file
    if instance.file:
        try:
            if default_storage.exists(instance.file.name):
                default_storage.delete(instance.file.name)
                print(f"Deleted file: {instance.file.name}")
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    # Delete thumbnail if exists
    # Implement if you add thumbnail field


# ============================================================================
# Document Version Signals
# ============================================================================

@receiver(pre_save, sender=DocumentVersion)
def version_pre_save(sender, instance, **kwargs):
    """
    Process version before saving.
    - Extract file metadata
    - Auto-increment version number
    """
    if instance.file:
        # Extract file size
        if not instance.file_size:
            instance.file_size = get_file_size(instance.file)
        
        # Auto-increment version number if not set
        if not instance.version_number and instance.document:
            last_version = DocumentVersion.objects.filter(
                document=instance.document
            ).order_by('-version_number').first()
            
            if last_version:
                instance.version_number = last_version.version_number + 1
            else:
                instance.version_number = 1


@receiver(post_save, sender=DocumentVersion)
def version_post_save(sender, instance, created, **kwargs):
    """
    Process version after saving.
    - Update document's updated_at timestamp
    - Send notifications
    """
    if created:
        # Update parent document's updated_at
        instance.document.updated_at = timezone.now()
        instance.document.save(update_fields=['updated_at'])
        
        # Log version creation
        print(f"Version {instance.version_number} created for document: {instance.document.title}")
        
        # TODO: Send notification to document watchers
        # notify_new_version(instance)


@receiver(post_delete, sender=DocumentVersion)
def version_post_delete(sender, instance, **kwargs):
    """
    Cleanup after version deletion.
    - Delete associated file
    """
    if instance.file:
        try:
            if default_storage.exists(instance.file.name):
                default_storage.delete(instance.file.name)
                print(f"Deleted version file: {instance.file.name}")
        except Exception as e:
            print(f"Error deleting version file: {e}")


# ============================================================================
# Document Share Signals
# ============================================================================

@receiver(post_save, sender=DocumentShare)
def share_post_save(sender, instance, created, **kwargs):
    """
    Process share after saving.
    - Send notification to shared user
    - Log share activity
    """
    if created:
        # Send notification
        try:
            notify_document_shared(instance)
        except Exception as e:
            print(f"Error sending share notification: {e}")
        
        # Log share activity
        print(f"Document '{instance.document.title}' shared with {instance.shared_with.username}")
        
        # TODO: Create audit log entry
        # create_audit_log('document_shared', instance)


@receiver(post_delete, sender=DocumentShare)
def share_post_delete(sender, instance, **kwargs):
    """
    Process share deletion.
    - Send notification about revoked access
    - Log activity
    """
    # Log share revocation
    print(f"Access revoked for {instance.shared_with.username} on document: {instance.document.title}")
    
    # TODO: Send notification
    # notify_share_revoked(instance)
    
    # TODO: Create audit log entry
    # create_audit_log('share_revoked', instance)


# ============================================================================
# Document Comment Signals
# ============================================================================

@receiver(post_save, sender=DocumentComment)
def comment_post_save(sender, instance, created, **kwargs):
    """
    Process comment after saving.
    - Send notifications
    - Update document activity timestamp
    """
    if created:
        # Send notification to document owner
        try:
            notify_document_comment(instance)
        except Exception as e:
            print(f"Error sending comment notification: {e}")
        
        # Update document's updated_at
        instance.document.updated_at = timezone.now()
        instance.document.save(update_fields=['updated_at'])
        
        # Log comment activity
        print(f"Comment added to document '{instance.document.title}' by {instance.user.username}")
        
        # TODO: Notify other commenters on the document
        # notify_comment_thread(instance)


# ============================================================================
# Document Tag Signals
# ============================================================================

@receiver(m2m_changed, sender=Document.tags.through)
def document_tags_changed(sender, instance, action, **kwargs):
    """
    Process tag changes on documents.
    - Log tag additions/removals
    - Update document search index
    """
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Update document's updated_at
        instance.updated_at = timezone.now()
        instance.save(update_fields=['updated_at'])
        
        # Log tag changes
        if action == 'post_add':
            print(f"Tags added to document: {instance.title}")
        elif action == 'post_remove':
            print(f"Tags removed from document: {instance.title}")
        elif action == 'post_clear':
            print(f"All tags cleared from document: {instance.title}")
        
        # TODO: Update search index if using Elasticsearch
        # update_document_search_index(instance)


# ============================================================================
# Document Category Signals (if you create this model)
# ============================================================================

# Note: These would be implemented if DocumentCategory model exists
# Placeholder for future implementation


# ============================================================================
# Cleanup and Maintenance Signals
# ============================================================================

@receiver(post_save, sender=Document)
def check_document_expiry(sender, instance, **kwargs):
    """
    Check if document has expired and auto-archive if needed.
    """
    if instance.expiry_date and not instance.is_archived:
        if instance.expiry_date < timezone.now().date():
            instance.is_archived = True
            instance.archived_at = timezone.now()
            instance.save(update_fields=['is_archived', 'archived_at'])
            print(f"Document '{instance.title}' auto-archived due to expiry")


@receiver(post_save, sender=DocumentShare)
def check_share_expiry(sender, instance, **kwargs):
    """
    Check if share has expired and delete if needed.
    """
    if instance.expires_at:
        if instance.expires_at < timezone.now():
            print(f"Share expired and deleted: {instance.document.title} for {instance.shared_with.username}")
            instance.delete()


# ============================================================================
# File Storage Management
# ============================================================================

@receiver(pre_save, sender=Document)
def check_storage_quota(sender, instance, **kwargs):
    """
    Check user storage quota before saving large files.
    Optional: Implement storage limits per user.
    """
    # TODO: Implement storage quota checking
    # if instance.file and instance.uploaded_by:
    #     user_usage = get_user_storage_usage(instance.uploaded_by)
    #     quota = get_user_storage_quota(instance.uploaded_by)
    #     
    #     new_size = get_file_size(instance.file)
    #     if user_usage['total_bytes'] + new_size > quota:
    #         raise ValidationError('Storage quota exceeded')
    pass


# ============================================================================
# Integration Signals
# ============================================================================

@receiver(post_save, sender=Document)
def sync_with_external_services(sender, instance, created, **kwargs):
    """
    Sync document with external services (cloud storage, search engines, etc.)
    """
    # TODO: Implement external service integrations
    # Examples:
    # - Upload to cloud backup (S3, Google Drive)
    # - Index in Elasticsearch for better search
    # - Sync with document management systems
    # - Trigger webhooks for third-party integrations
    pass


@receiver(post_save, sender=Document)
def create_activity_log(sender, instance, created, **kwargs):
    """
    Create activity log entries for document actions.
    Integrates with audit app if available.
    """
    try:
        from apps.audit.models import AuditLog
        
        action = 'created' if created else 'updated'
        
        AuditLog.objects.create(
            user=instance.uploaded_by,
            action=f'document_{action}',
            model_name='Document',
            object_id=instance.pk,
            details={
                'title': instance.title,
                'category': instance.category.name if instance.category else None,
                'file_type': instance.file_type,
                'is_public': instance.is_public,
            }
        )
    except ImportError:
        # Audit app not available
        pass
    except Exception as e:
        print(f"Error creating audit log: {e}")


@receiver(post_save, sender=DocumentShare)
def create_share_activity_log(sender, instance, created, **kwargs):
    """
    Log document sharing activities.
    """
    if created:
        try:
            from apps.audit.models import AuditLog
            
            AuditLog.objects.create(
                user=instance.shared_by,
                action='document_shared',
                model_name='Document',
                object_id=instance.document.pk,
                details={
                    'document_title': instance.document.title,
                    'shared_with': instance.shared_with.username,
                    'can_edit': instance.can_edit,
                    'can_delete': instance.can_delete,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating share audit log: {e}")


@receiver(post_delete, sender=Document)
def create_deletion_log(sender, instance, **kwargs):
    """
    Log document deletions.
    """
    try:
        from apps.audit.models import AuditLog
        
        # Note: Can't use instance.uploaded_by after deletion in some cases
        # This should be called before actual deletion if you need user info
        AuditLog.objects.create(
            user=instance.uploaded_by if hasattr(instance, 'uploaded_by') else None,
            action='document_deleted',
            model_name='Document',
            object_id=instance.pk,
            details={
                'title': instance.title,
                'file_name': instance.file_name,
                'file_type': instance.file_type,
            }
        )
    except ImportError:
        pass
    except Exception as e:
        print(f"Error creating deletion audit log: {e}")


# ============================================================================
# Signal Connection
# ============================================================================

# All signals are automatically connected via @receiver decorator
# To disconnect a signal for testing:
# post_save.disconnect(document_post_save, sender=Document)

# To manually connect a signal:
# post_save.connect(document_post_save, sender=Document)