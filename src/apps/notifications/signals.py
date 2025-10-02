"""
Notifications App - Signal Handlers
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Notification,
    NotificationPreference,
    NotificationLog,
    NotificationSchedule
)
from .utils import deliver_notification

User = get_user_model()


# ============================================================================
# USER SIGNALS
# ============================================================================

@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences for new users"""
    
    if created:
        NotificationPreference.objects.get_or_create(user=instance)


# ============================================================================
# NOTIFICATION SIGNALS
# ============================================================================

@receiver(post_save, sender=Notification)
def notification_post_save(sender, instance, created, **kwargs):
    """Handle actions after notification is saved"""
    
    if created:
        handle_new_notification(instance)


def handle_new_notification(notification):
    """Handle new notification creation"""
    
    # Deliver notification via configured methods
    if not notification.is_sent:
        deliver_notification(notification)


@receiver(pre_save, sender=Notification)
def notification_pre_save(sender, instance, **kwargs):
    """Handle actions before notification is saved"""
    
    if instance.pk:
        try:
            old_instance = Notification.objects.get(pk=instance.pk)
            
            # Track if status changed
            if old_instance.is_read != instance.is_read:
                instance._read_status_changed = True
            
        except Notification.DoesNotExist:
            pass


# ============================================================================
# NOTIFICATION PREFERENCE SIGNALS
# ============================================================================

@receiver(post_save, sender=NotificationPreference)
def preference_post_save(sender, instance, created, **kwargs):
    """Handle actions after preference is saved"""
    
    if not created:
        # Preferences updated
        pass


# ============================================================================
# NOTIFICATION LOG SIGNALS
# ============================================================================

@receiver(post_save, sender=NotificationLog)
def log_post_save(sender, instance, created, **kwargs):
    """Handle actions after log is saved"""
    
    if created:
        # New delivery attempt logged
        pass
    
    # Update notification delivery status
    if instance.status == 'sent':
        notification = instance.notification
        
        if instance.delivery_method == 'email' and not notification.email_sent:
            notification.email_sent = True
            notification.save(update_fields=['email_sent'])
        
        elif instance.delivery_method == 'sms' and not notification.sms_sent:
            notification.sms_sent = True
            notification.save(update_fields=['sms_sent'])
        
        elif instance.delivery_method == 'push' and not notification.push_sent:
            notification.push_sent = True
            notification.save(update_fields=['push_sent'])


# ============================================================================
# NOTIFICATION SCHEDULE SIGNALS
# ============================================================================

@receiver(post_save, sender=NotificationSchedule)
def schedule_post_save(sender, instance, created, **kwargs):
    """Handle actions after schedule is saved"""
    
    if created:
        # New schedule created
        if not instance.next_run:
            instance.next_run = instance.scheduled_time
            instance.save(update_fields=['next_run'])


@receiver(pre_save, sender=NotificationSchedule)
def schedule_pre_save(sender, instance, **kwargs):
    """Handle actions before schedule is saved"""
    
    if instance.pk:
        try:
            old_instance = NotificationSchedule.objects.get(pk=instance.pk)
            
            # If scheduled time changed, update next_run
            if old_instance.scheduled_time != instance.scheduled_time:
                instance.next_run = instance.scheduled_time
        
        except NotificationSchedule.DoesNotExist:
            pass