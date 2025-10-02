"""
Repossessions App - Signal Handlers
Handles automated actions when repossession events occur
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Repossession, RepossessionDocument, RepossessionNote
from apps.vehicles.models import Vehicle
from apps.notifications.models import Notification
from apps.audit.models import AuditLog

User = get_user_model()


# ============================================================================
# REPOSSESSION SIGNALS
# ============================================================================

@receiver(pre_save, sender=Repossession)
def repossession_pre_save(sender, instance, **kwargs):
    """
    Handle actions before repossession is saved
    - Track status changes
    - Set timestamps
    """
    if instance.pk:  # Existing repossession
        try:
            old_instance = Repossession.objects.get(pk=instance.pk)
            
            # Track status change
            if old_instance.status != instance.status:
                instance.status_changed_at = timezone.now()
                
                # Store previous status for post_save signal
                instance._previous_status = old_instance.status
        except Repossession.DoesNotExist:
            pass
    else:
        # New repossession
        instance.initiated_at = timezone.now()


@receiver(post_save, sender=Repossession)
def repossession_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after repossession is saved
    - Update vehicle status
    - Send notifications
    - Create audit logs
    """
    if created:
        # New repossession created
        handle_new_repossession(instance)
    else:
        # Existing repossession updated
        handle_repossession_update(instance)


def handle_new_repossession(repossession):
    """Handle new repossession creation"""
    
    # Update vehicle status to 'repossessed'
    if repossession.vehicle:
        vehicle = repossession.vehicle
        vehicle.status = 'repossessed'
        vehicle.save(update_fields=['status'])
    
    # Notify assigned agent
    if repossession.assigned_to:
        Notification.objects.create(
            user=repossession.assigned_to,
            title='New Repossession Assignment',
            message=f'You have been assigned to repossession case #{repossession.case_number} for vehicle {repossession.vehicle}',
            notification_type='repossession',
            related_object_type='repossession',
            related_object_id=repossession.id,
            priority='high'
        )
    
    # Notify management/admin users
    admin_users = User.objects.filter(
        is_staff=True,
        is_active=True
    ).exclude(id=repossession.assigned_to.id if repossession.assigned_to else None)
    
    for admin in admin_users:
        Notification.objects.create(
            user=admin,
            title='New Repossession Initiated',
            message=f'Repossession case #{repossession.case_number} has been initiated for vehicle {repossession.vehicle}',
            notification_type='repossession',
            related_object_type='repossession',
            related_object_id=repossession.id,
            priority='medium'
        )
    
    # Create audit log
    AuditLog.objects.create(
        user=repossession.initiated_by,
        action='CREATE',
        model_name='Repossession',
        object_id=repossession.id,
        object_repr=str(repossession),
        changes={
            'case_number': repossession.case_number,
            'vehicle': str(repossession.vehicle),
            'client': str(repossession.client),
            'reason': repossession.reason,
            'status': repossession.status
        },
        ip_address=getattr(repossession, '_ip_address', None)
    )


def handle_repossession_update(repossession):
    """Handle repossession updates"""
    
    # Check if status changed
    previous_status = getattr(repossession, '_previous_status', None)
    
    if previous_status and previous_status != repossession.status:
        handle_status_change(repossession, previous_status)
    
    # Create audit log for update
    if hasattr(repossession, '_changed_by'):
        AuditLog.objects.create(
            user=repossession._changed_by,
            action='UPDATE',
            model_name='Repossession',
            object_id=repossession.id,
            object_repr=str(repossession),
            changes={
                'previous_status': previous_status,
                'new_status': repossession.status,
                'updated_at': str(timezone.now())
            },
            ip_address=getattr(repossession, '_ip_address', None)
        )


def handle_status_change(repossession, previous_status):
    """Handle repossession status changes"""
    
    status_messages = {
        'initiated': 'Repossession has been initiated',
        'assigned': 'Agent has been assigned to the case',
        'in_progress': 'Repossession is in progress',
        'vehicle_located': 'Vehicle has been located',
        'vehicle_recovered': 'Vehicle has been recovered',
        'completed': 'Repossession has been completed',
        'cancelled': 'Repossession has been cancelled',
        'failed': 'Repossession attempt failed'
    }
    
    # Update vehicle status based on repossession status
    if repossession.vehicle:
        vehicle = repossession.vehicle
        
        if repossession.status == 'vehicle_recovered':
            vehicle.status = 'in_stock'
            vehicle.save(update_fields=['status'])
        elif repossession.status == 'completed':
            vehicle.status = 'available'
            vehicle.save(update_fields=['status'])
        elif repossession.status == 'cancelled':
            vehicle.status = 'active'  # Return to active status
            vehicle.save(update_fields=['status'])
    
    # Notify assigned agent
    if repossession.assigned_to:
        Notification.objects.create(
            user=repossession.assigned_to,
            title=f'Repossession Status Updated: {repossession.get_status_display()}',
            message=f'Case #{repossession.case_number}: {status_messages.get(repossession.status, "Status updated")}',
            notification_type='repossession',
            related_object_type='repossession',
            related_object_id=repossession.id,
            priority='high' if repossession.status in ['vehicle_recovered', 'completed'] else 'medium'
        )
    
    # Notify client for specific statuses
    if repossession.status in ['vehicle_recovered', 'completed'] and repossession.client:
        # Send notification to client (if they have a user account)
        if hasattr(repossession.client, 'user') and repossession.client.user:
            Notification.objects.create(
                user=repossession.client.user,
                title='Repossession Update',
                message=f'The repossession case for your vehicle has been {repossession.get_status_display().lower()}',
                notification_type='repossession',
                related_object_type='repossession',
                related_object_id=repossession.id,
                priority='high'
            )
    
    # Notify management for critical statuses
    if repossession.status in ['vehicle_recovered', 'completed', 'failed']:
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title=f'Repossession {repossession.get_status_display()}',
                message=f'Case #{repossession.case_number} for {repossession.vehicle} is now {repossession.get_status_display().lower()}',
                notification_type='repossession',
                related_object_type='repossession',
                related_object_id=repossession.id,
                priority='high'
            )


@receiver(post_delete, sender=Repossession)
def repossession_post_delete(sender, instance, **kwargs):
    """
    Handle actions after repossession is deleted
    - Revert vehicle status
    - Create audit log
    """
    # Revert vehicle status
    if instance.vehicle:
        vehicle = instance.vehicle
        vehicle.status = 'active'  # Return to active
        vehicle.save(update_fields=['status'])
    
    # Create audit log
    if hasattr(instance, '_deleted_by'):
        AuditLog.objects.create(
            user=instance._deleted_by,
            action='DELETE',
            model_name='Repossession',
            object_id=instance.id,
            object_repr=str(instance),
            changes={
                'case_number': instance.case_number,
                'vehicle': str(instance.vehicle),
                'status': instance.status,
                'deleted_at': str(timezone.now())
            },
            ip_address=getattr(instance, '_ip_address', None)
        )


# ============================================================================
# REPOSSESSION DOCUMENT SIGNALS
# ============================================================================

@receiver(post_save, sender=RepossessionDocument)
def repossession_document_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after repossession document is saved
    - Notify relevant users
    - Create audit log
    """
    if created:
        # Notify assigned agent
        if instance.repossession.assigned_to:
            Notification.objects.create(
                user=instance.repossession.assigned_to,
                title='New Document Added',
                message=f'A new {instance.document_type} document has been added to case #{instance.repossession.case_number}',
                notification_type='document',
                related_object_type='repossession',
                related_object_id=instance.repossession.id,
                priority='medium'
            )
        
        # Create audit log
        if hasattr(instance, '_uploaded_by'):
            AuditLog.objects.create(
                user=instance._uploaded_by,
                action='CREATE',
                model_name='RepossessionDocument',
                object_id=instance.id,
                object_repr=str(instance),
                changes={
                    'repossession': str(instance.repossession),
                    'document_type': instance.document_type,
                    'file_name': instance.file.name if instance.file else None
                }
            )


# ============================================================================
# REPOSSESSION NOTE SIGNALS
# ============================================================================

@receiver(post_save, sender=RepossessionNote)
def repossession_note_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after repossession note is saved
    - Notify relevant users if note is important
    """
    if created and instance.is_important:
        # Notify assigned agent if note is marked as important
        if instance.repossession.assigned_to and instance.created_by != instance.repossession.assigned_to:
            Notification.objects.create(
                user=instance.repossession.assigned_to,
                title='Important Note Added',
                message=f'An important note has been added to case #{instance.repossession.case_number}',
                notification_type='note',
                related_object_type='repossession',
                related_object_id=instance.repossession.id,
                priority='high'
            )
        
        # Notify management
        admin_users = User.objects.filter(
            is_staff=True,
            is_active=True
        ).exclude(id=instance.created_by.id)
        
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='Important Repossession Note',
                message=f'Important note added to case #{instance.repossession.case_number} by {instance.created_by.get_full_name()}',
                notification_type='note',
                related_object_type='repossession',
                related_object_id=instance.repossession.id,
                priority='medium'
            )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def send_repossession_reminder(repossession):
    """
    Send reminder notifications for pending repossessions
    Can be called from scheduled tasks
    """
    if repossession.assigned_to and repossession.status in ['assigned', 'in_progress']:
        days_pending = (timezone.now().date() - repossession.initiated_at.date()).days
        
        if days_pending > 7:  # More than 7 days pending
            Notification.objects.create(
                user=repossession.assigned_to,
                title='Repossession Case Reminder',
                message=f'Case #{repossession.case_number} has been pending for {days_pending} days. Please update the status.',
                notification_type='reminder',
                related_object_type='repossession',
                related_object_id=repossession.id,
                priority='high'
            )


def check_overdue_repossessions():
    """
    Check for overdue repossessions and send alerts
    Should be called from a scheduled task (e.g., Celery beat)
    """
    from datetime import timedelta
    
    overdue_threshold = timezone.now() - timedelta(days=14)
    
    overdue_repossessions = Repossession.objects.filter(
        status__in=['assigned', 'in_progress', 'vehicle_located'],
        initiated_at__lt=overdue_threshold
    )
    
    for repossession in overdue_repossessions:
        # Notify assigned agent
        if repossession.assigned_to:
            Notification.objects.create(
                user=repossession.assigned_to,
                title='URGENT: Overdue Repossession Case',
                message=f'Case #{repossession.case_number} is overdue. Immediate action required.',
                notification_type='alert',
                related_object_type='repossession',
                related_object_id=repossession.id,
                priority='urgent'
            )
        
        # Notify management
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='Overdue Repossession Alert',
                message=f'Case #{repossession.case_number} assigned to {repossession.assigned_to.get_full_name() if repossession.assigned_to else "N/A"} is overdue',
                notification_type='alert',
                related_object_type='repossession',
                related_object_id=repossession.id,
                priority='urgent'
            )