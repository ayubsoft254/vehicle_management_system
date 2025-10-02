"""
Notifications App - Background Tasks (Celery)
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import logging

from .models import (
    Notification,
    NotificationPreference,
    NotificationSchedule,
    NotificationLog
)
from .utils import (
    send_email_notification,
    send_sms_notification,
    send_push_notification,
    send_email_digest,
    cleanup_old_notifications,
    cleanup_expired_notifications,
    deliver_notification,
    process_pending_notifications,
    process_email_digests
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================================
# NOTIFICATION DELIVERY TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_notification_email(self, notification_id):
    """
    Send notification via email
    
    Args:
        notification_id: Notification UUID
    """
    
    try:
        notification = Notification.objects.get(id=notification_id)
        success = send_email_notification(notification)
        
        if not success:
            raise Exception("Failed to send email notification")
        
        return {'status': 'sent', 'notification_id': str(notification_id)}
    
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'status': 'error', 'message': 'Notification not found'}
    
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        
        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=3)
def send_notification_sms(self, notification_id):
    """
    Send notification via SMS
    
    Args:
        notification_id: Notification UUID
    """
    
    try:
        notification = Notification.objects.get(id=notification_id)
        success = send_sms_notification(notification)
        
        if not success:
            raise Exception("Failed to send SMS notification")
        
        return {'status': 'sent', 'notification_id': str(notification_id)}
    
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'status': 'error', 'message': 'Notification not found'}
    
    except Exception as e:
        logger.error(f"Error sending SMS notification: {e}")
        
        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=3)
def send_notification_push(self, notification_id):
    """
    Send push notification
    
    Args:
        notification_id: Notification UUID
    """
    
    try:
        notification = Notification.objects.get(id=notification_id)
        success = send_push_notification(notification)
        
        if not success:
            raise Exception("Failed to send push notification")
        
        return {'status': 'sent', 'notification_id': str(notification_id)}
    
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'status': 'error', 'message': 'Notification not found'}
    
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        
        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


@shared_task
def deliver_notification_task(notification_id):
    """
    Deliver notification via all configured methods
    
    Args:
        notification_id: Notification UUID
    """
    
    try:
        notification = Notification.objects.get(id=notification_id)
        results = deliver_notification(notification)
        
        return {
            'status': 'completed',
            'notification_id': str(notification_id),
            'results': results
        }
    
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'status': 'error', 'message': 'Notification not found'}
    
    except Exception as e:
        logger.error(f"Error delivering notification: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# BULK NOTIFICATION TASKS
# ============================================================================

@shared_task
def send_bulk_notifications(user_ids, title, message, notification_type='info', priority='medium'):
    """
    Send notifications to multiple users
    
    Args:
        user_ids: List of user IDs
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        priority: Priority level
    """
    
    from .utils import create_notification
    
    count = 0
    errors = []
    
    users = User.objects.filter(id__in=user_ids)
    
    for user in users:
        try:
            notification = create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
            
            if notification:
                count += 1
        
        except Exception as e:
            logger.error(f"Error creating notification for user {user.id}: {e}")
            errors.append({'user_id': user.id, 'error': str(e)})
    
    return {
        'status': 'completed',
        'sent': count,
        'errors': len(errors),
        'error_details': errors
    }


# ============================================================================
# SCHEDULED TASKS (CELERY BEAT)
# ============================================================================

@shared_task
def process_pending_notifications_task():
    """
    Process pending notifications for delivery
    Scheduled to run every 5 minutes
    """
    
    count = process_pending_notifications()
    
    logger.info(f"Processed {count} pending notifications")
    
    return {'status': 'completed', 'processed': count}


@shared_task
def process_notification_schedules():
    """
    Process scheduled notifications
    Scheduled to run every 5 minutes
    """
    
    now = timezone.now()
    
    # Get schedules that are due
    schedules = NotificationSchedule.objects.filter(
        is_active=True,
        status='active',
        next_run__lte=now
    )
    
    count = 0
    
    for schedule in schedules:
        try:
            # Get recipients
            users = schedule.users.all()
            
            # Use template or manual content
            if schedule.template:
                for user in users:
                    from .utils import create_notification_from_template
                    create_notification_from_template(user, schedule.template)
            else:
                for user in users:
                    from .utils import create_notification
                    create_notification(
                        user=user,
                        title=schedule.title,
                        message=schedule.message,
                        notification_type=schedule.notification_type
                    )
            
            # Update schedule
            schedule.last_run = now
            
            # Calculate next run based on frequency
            if schedule.frequency == 'once':
                schedule.status = 'completed'
                schedule.is_active = False
            elif schedule.frequency == 'daily':
                schedule.next_run = now + timedelta(days=1)
            elif schedule.frequency == 'weekly':
                schedule.next_run = now + timedelta(weeks=1)
            elif schedule.frequency == 'monthly':
                schedule.next_run = now + timedelta(days=30)
            
            schedule.save()
            count += 1
        
        except Exception as e:
            logger.error(f"Error processing schedule {schedule.id}: {e}")
    
    logger.info(f"Processed {count} notification schedules")
    
    return {'status': 'completed', 'processed': count}


@shared_task
def send_email_digests_task():
    """
    Send daily email digests
    Scheduled to run once daily at digest time
    """
    
    count = process_email_digests()
    
    logger.info(f"Sent {count} email digests")
    
    return {'status': 'completed', 'sent': count}


@shared_task
def cleanup_old_notifications_task():
    """
    Clean up old read notifications
    Scheduled to run daily
    """
    
    count = cleanup_old_notifications(days=90)
    
    logger.info(f"Cleaned up {count} old notifications")
    
    return {'status': 'completed', 'deleted': count}


@shared_task
def cleanup_expired_notifications_task():
    """
    Clean up expired notifications
    Scheduled to run hourly
    """
    
    count = cleanup_expired_notifications()
    
    logger.info(f"Cleaned up {count} expired notifications")
    
    return {'status': 'completed', 'deleted': count}


@shared_task
def retry_failed_deliveries():
    """
    Retry failed notification deliveries
    Scheduled to run every hour
    """
    
    # Get failed logs from last 24 hours with retry count < 3
    yesterday = timezone.now() - timedelta(days=1)
    
    failed_logs = NotificationLog.objects.filter(
        status='failed',
        created_at__gte=yesterday,
        retry_count__lt=3
    )
    
    count = 0
    
    for log in failed_logs:
        try:
            notification = log.notification
            
            # Retry based on delivery method
            if log.delivery_method == 'email':
                send_notification_email.delay(str(notification.id))
            elif log.delivery_method == 'sms':
                send_notification_sms.delay(str(notification.id))
            elif log.delivery_method == 'push':
                send_notification_push.delay(str(notification.id))
            
            count += 1
        
        except Exception as e:
            logger.error(f"Error retrying failed delivery: {e}")
    
    logger.info(f"Retried {count} failed deliveries")
    
    return {'status': 'completed', 'retried': count}


# ============================================================================
# NOTIFICATION STATISTICS TASKS
# ============================================================================

@shared_task
def generate_notification_report():
    """
    Generate daily notification statistics report
    Scheduled to run daily
    """
    
    from .utils import get_notification_stats, get_delivery_stats
    
    yesterday = timezone.now() - timedelta(days=1)
    
    # Get stats
    all_stats = get_notification_stats()
    delivery_stats = get_delivery_stats()
    
    # Get yesterday's notifications
    yesterday_notifications = Notification.objects.filter(
        created_at__date=yesterday.date()
    )
    
    report = {
        'date': yesterday.date().isoformat(),
        'total_notifications': yesterday_notifications.count(),
        'overall_stats': all_stats,
        'delivery_stats': delivery_stats,
    }
    
    # TODO: Send report to admins or save to file
    logger.info(f"Generated notification report: {report}")
    
    return report


# ============================================================================
# UTILITY TASKS
# ============================================================================

@shared_task
def mark_stale_notifications_as_read():
    """
    Mark old unread notifications as read
    Scheduled to run weekly
    """
    
    cutoff = timezone.now() - timedelta(days=30)
    
    count = Notification.objects.filter(
        is_read=False,
        priority='low',
        created_at__lt=cutoff
    ).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    logger.info(f"Marked {count} stale notifications as read")
    
    return {'status': 'completed', 'marked': count}


@shared_task
def send_notification_reminders():
    """
    Send reminders for unread urgent notifications
    Scheduled to run every 6 hours
    """
    
    # Get urgent notifications older than 6 hours that are unread
    six_hours_ago = timezone.now() - timedelta(hours=6)
    
    urgent_notifications = Notification.objects.filter(
        priority='urgent',
        is_read=False,
        created_at__lt=six_hours_ago,
        created_at__gte=six_hours_ago - timedelta(hours=6)  # Only once
    )
    
    count = 0
    
    for notification in urgent_notifications:
        # Create reminder notification
        from .utils import create_notification
        
        create_notification(
            user=notification.user,
            title=f"Reminder: {notification.title}",
            message=f"You have an unread urgent notification: {notification.message[:100]}",
            notification_type='reminder',
            priority='high',
            related_object_id=notification.id
        )
        
        count += 1
    
    logger.info(f"Sent {count} notification reminders")
    
    return {'status': 'completed', 'sent': count}


@shared_task
def update_notification_statistics():
    """
    Update cached notification statistics
    Scheduled to run every hour
    """
    
    from django.core.cache import cache
    from .utils import get_notification_stats, get_delivery_stats
    
    # Cache overall stats
    cache.set('notification_stats', get_notification_stats(), timeout=3600)
    cache.set('delivery_stats', get_delivery_stats(), timeout=3600)
    
    # Cache per-user unread counts
    users_with_notifications = User.objects.filter(
        notifications__is_read=False
    ).distinct()
    
    for user in users_with_notifications:
        count = Notification.objects.filter(user=user, is_read=False).count()
        cache.set(f'unread_count_{user.id}', count, timeout=3600)
    
    logger.info("Updated notification statistics cache")
    
    return {'status': 'completed'}