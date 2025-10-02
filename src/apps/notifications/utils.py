"""
Notifications App - Utility Functions
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import timedelta
import logging

from .models import (
    Notification,
    NotificationPreference,
    NotificationLog,
    NotificationTemplate
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================================
# NOTIFICATION CREATION HELPERS
# ============================================================================

def create_notification(user, title, message, notification_type='info', priority='medium', **kwargs):
    """
    Create a notification for a user
    
    Args:
        user: User object
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        priority: Priority level
        **kwargs: Additional fields (action_url, action_text, metadata, etc.)
    
    Returns:
        Notification object
    """
    
    # Get user preferences
    preference = get_user_preferences(user)
    
    # Check if user should receive notification
    if not preference.should_notify(notification_type, priority):
        return None
    
    # Get delivery methods
    delivery_methods = preference.get_delivery_methods(priority)
    
    # Create notification
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        delivery_methods=delivery_methods,
        **kwargs
    )
    
    return notification


def create_bulk_notification(users, title, message, notification_type='info', priority='medium', **kwargs):
    """
    Create notifications for multiple users
    
    Args:
        users: QuerySet or list of User objects
        title, message, notification_type, priority: Notification details
        **kwargs: Additional fields
    
    Returns:
        List of created Notification objects
    """
    
    notifications = []
    
    for user in users:
        notification = create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            **kwargs
        )
        if notification:
            notifications.append(notification)
    
    return notifications


def create_notification_from_template(user, template, context=None):
    """
    Create notification from template
    
    Args:
        user: User object
        template: NotificationTemplate object or template name
        context: Dictionary of context variables
    
    Returns:
        Notification object
    """
    
    if isinstance(template, str):
        template = NotificationTemplate.objects.get(name=template, is_active=True)
    
    if context is None:
        context = {}
    
    # Add default context
    context.setdefault('user', user)
    
    # Render template
    rendered = template.render(context)
    
    # Create notification
    notification = create_notification(
        user=user,
        title=rendered['title'],
        message=rendered['message'],
        notification_type=template.notification_type,
        priority=template.priority
    )
    
    return notification


# ============================================================================
# USER PREFERENCE HELPERS
# ============================================================================

def get_user_preferences(user):
    """Get or create user notification preferences"""
    
    preference, created = NotificationPreference.objects.get_or_create(user=user)
    return preference


def update_user_preferences(user, **kwargs):
    """Update user notification preferences"""
    
    preference = get_user_preferences(user)
    
    for key, value in kwargs.items():
        if hasattr(preference, key):
            setattr(preference, key, value)
    
    preference.save()
    return preference


# ============================================================================
# EMAIL NOTIFICATION HELPERS
# ============================================================================

def send_email_notification(notification):
    """
    Send notification via email
    
    Args:
        notification: Notification object
    
    Returns:
        bool: True if sent successfully
    """
    
    user = notification.user
    preference = get_user_preferences(user)
    
    # Check if email is enabled
    if not preference.email_enabled:
        return False
    
    # Get email address
    email_address = preference.email_address or user.email
    if not email_address:
        logger.warning(f"No email address for user {user.username}")
        return False
    
    # Check quiet hours
    if preference.is_quiet_hours() and notification.priority != 'urgent':
        logger.info(f"Skipping email for user {user.username} - quiet hours")
        return False
    
    try:
        # Prepare email
        subject = f"[{notification.get_priority_display()}] {notification.title}"
        
        # Plain text
        text_content = notification.message
        
        # HTML content
        html_content = render_to_string('notifications/emails/notification_email.html', {
            'notification': notification,
            'user': user,
        })
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_address]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        # Log delivery
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='email',
            status='sent',
            recipient=email_address,
            sent_at=timezone.now()
        )
        
        # Update notification
        notification.email_sent = True
        notification.save(update_fields=['email_sent'])
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        
        # Log failure
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='email',
            status='failed',
            recipient=email_address,
            error_message=str(e)
        )
        
        return False


def send_email_digest(user, notifications):
    """
    Send daily email digest
    
    Args:
        user: User object
        notifications: QuerySet of notifications
    
    Returns:
        bool: True if sent successfully
    """
    
    preference = get_user_preferences(user)
    
    if not preference.email_enabled or not preference.email_digest:
        return False
    
    email_address = preference.email_address or user.email
    if not email_address:
        return False
    
    try:
        subject = f"Your Daily Notification Digest - {notifications.count()} notifications"
        
        html_content = render_to_string('notifications/emails/digest_email.html', {
            'user': user,
            'notifications': notifications,
            'date': timezone.now().date()
        })
        
        text_content = f"You have {notifications.count()} notifications."
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_address]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email digest: {e}")
        return False


# ============================================================================
# SMS NOTIFICATION HELPERS
# ============================================================================

def send_sms_notification(notification):
    """
    Send notification via SMS
    
    Args:
        notification: Notification object
    
    Returns:
        bool: True if sent successfully
    """
    
    user = notification.user
    preference = get_user_preferences(user)
    
    # Check if SMS is enabled
    if not preference.sms_enabled:
        return False
    
    phone_number = preference.phone_number
    if not phone_number:
        logger.warning(f"No phone number for user {user.username}")
        return False
    
    # Only send SMS for high priority
    if notification.priority not in ['high', 'urgent']:
        return False
    
    try:
        # Format SMS message
        sms_message = f"{notification.title}: {notification.message[:100]}"
        
        # Send SMS (implement with your SMS provider)
        # Example: Twilio, AWS SNS, etc.
        send_sms(phone_number, sms_message)
        
        # Log delivery
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='sms',
            status='sent',
            recipient=phone_number,
            sent_at=timezone.now()
        )
        
        # Update notification
        notification.sms_sent = True
        notification.save(update_fields=['sms_sent'])
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to send SMS notification: {e}")
        
        # Log failure
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='sms',
            status='failed',
            recipient=phone_number,
            error_message=str(e)
        )
        
        return False


def send_sms(phone_number, message):
    """
    Send SMS using configured provider
    
    Args:
        phone_number: Phone number
        message: SMS message text
    
    Returns:
        bool: True if sent successfully
    """
    
    # TODO: Implement with your SMS provider
    # Example implementations:
    
    # Twilio
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # client.messages.create(
    #     body=message,
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )
    
    # AWS SNS
    # import boto3
    # sns = boto3.client('sns')
    # sns.publish(PhoneNumber=phone_number, Message=message)
    
    logger.info(f"SMS sent to {phone_number}: {message}")
    return True


# ============================================================================
# PUSH NOTIFICATION HELPERS
# ============================================================================

def send_push_notification(notification):
    """
    Send push notification
    
    Args:
        notification: Notification object
    
    Returns:
        bool: True if sent successfully
    """
    
    user = notification.user
    preference = get_user_preferences(user)
    
    if not preference.push_enabled:
        return False
    
    try:
        # TODO: Implement with your push notification provider
        # Example: Firebase Cloud Messaging, OneSignal, etc.
        
        # Log delivery
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='push',
            status='sent',
            recipient=user.username,
            sent_at=timezone.now()
        )
        
        # Update notification
        notification.push_sent = True
        notification.save(update_fields=['push_sent'])
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        
        NotificationLog.objects.create(
            notification=notification,
            delivery_method='push',
            status='failed',
            recipient=user.username,
            error_message=str(e)
        )
        
        return False


# ============================================================================
# NOTIFICATION DELIVERY
# ============================================================================

def deliver_notification(notification):
    """
    Deliver notification via all configured methods
    
    Args:
        notification: Notification object
    
    Returns:
        dict: Delivery results
    """
    
    results = {
        'in_app': True,  # Already created
        'email': False,
        'sms': False,
        'push': False,
    }
    
    delivery_methods = notification.delivery_methods or []
    
    if 'email' in delivery_methods:
        results['email'] = send_email_notification(notification)
    
    if 'sms' in delivery_methods:
        results['sms'] = send_sms_notification(notification)
    
    if 'push' in delivery_methods:
        results['push'] = send_push_notification(notification)
    
    # Update notification as sent
    if any(results.values()):
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save(update_fields=['is_sent', 'sent_at'])
    
    return results


def process_pending_notifications():
    """
    Process pending notifications for delivery
    Should be called from scheduled task
    
    Returns:
        int: Number of notifications processed
    """
    
    pending = Notification.objects.filter(is_sent=False)
    count = 0
    
    for notification in pending:
        deliver_notification(notification)
        count += 1
    
    return count


# ============================================================================
# NOTIFICATION CLEANUP
# ============================================================================

def cleanup_old_notifications(days=90):
    """
    Delete old read notifications
    
    Args:
        days: Number of days to keep
    
    Returns:
        int: Number of notifications deleted
    """
    
    cutoff = timezone.now() - timedelta(days=days)
    count = Notification.objects.filter(
        created_at__lt=cutoff,
        is_read=True
    ).delete()[0]
    
    return count


def cleanup_expired_notifications():
    """
    Delete expired notifications
    
    Returns:
        int: Number of notifications deleted
    """
    
    count = Notification.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()[0]
    
    return count


# ============================================================================
# NOTIFICATION QUERIES
# ============================================================================

def get_unread_count(user):
    """Get unread notification count for user"""
    return Notification.objects.filter(user=user, is_read=False).count()


def get_urgent_notifications(user):
    """Get urgent unread notifications for user"""
    return Notification.objects.filter(
        user=user,
        priority='urgent',
        is_read=False
    )


def get_recent_notifications(user, days=7, limit=10):
    """Get recent notifications for user"""
    cutoff = timezone.now() - timedelta(days=days)
    return Notification.objects.filter(
        user=user,
        created_at__gte=cutoff
    ).order_by('-created_at')[:limit]


def search_notifications(user, query):
    """Search user notifications"""
    return Notification.objects.filter(
        user=user
    ).filter(
        Q(title__icontains=query) |
        Q(message__icontains=query)
    )


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

def mark_all_as_read(user):
    """Mark all notifications as read for user"""
    return Notification.objects.filter(
        user=user,
        is_read=False
    ).update(
        is_read=True,
        read_at=timezone.now()
    )


def delete_all_read(user):
    """Delete all read notifications for user"""
    return Notification.objects.filter(
        user=user,
        is_read=True
    ).delete()[0]


# ============================================================================
# STATISTICS
# ============================================================================

def get_notification_stats(user=None):
    """
    Get notification statistics
    
    Args:
        user: User object (optional, None for system-wide stats)
    
    Returns:
        dict: Statistics
    """
    
    qs = Notification.objects.all()
    if user:
        qs = qs.filter(user=user)
    
    stats = {
        'total': qs.count(),
        'unread': qs.filter(is_read=False).count(),
        'sent': qs.filter(is_sent=True).count(),
        'by_type': {},
        'by_priority': {},
    }
    
    # By type
    from django.db.models import Count
    by_type = qs.values('notification_type').annotate(count=Count('id'))
    for item in by_type:
        stats['by_type'][item['notification_type']] = item['count']
    
    # By priority
    by_priority = qs.values('priority').annotate(count=Count('id'))
    for item in by_priority:
        stats['by_priority'][item['priority']] = item['count']
    
    return stats


def get_delivery_stats():
    """Get notification delivery statistics"""
    
    from django.db.models import Count
    
    logs = NotificationLog.objects.all()
    
    stats = {
        'total': logs.count(),
        'by_method': {},
        'by_status': {},
        'success_rate': 0,
    }
    
    # By method
    by_method = logs.values('delivery_method').annotate(count=Count('id'))
    for item in by_method:
        stats['by_method'][item['delivery_method']] = item['count']
    
    # By status
    by_status = logs.values('status').annotate(count=Count('id'))
    for item in by_status:
        stats['by_status'][item['status']] = item['count']
    
    # Success rate
    total = logs.count()
    if total > 0:
        successful = logs.filter(status__in=['sent', 'delivered']).count()
        stats['success_rate'] = (successful / total) * 100
    
    return stats


# ============================================================================
# EMAIL DIGEST PROCESSING
# ============================================================================

def process_email_digests():
    """
    Process and send email digests
    Should be called from scheduled task at digest time
    
    Returns:
        int: Number of digests sent
    """
    
    # Get users with digest enabled
    preferences = NotificationPreference.objects.filter(
        email_enabled=True,
        email_digest=True
    )
    
    count = 0
    
    for preference in preferences:
        # Get unread notifications from last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        notifications = Notification.objects.filter(
            user=preference.user,
            is_read=False,
            created_at__gte=yesterday
        )
        
        if notifications.exists():
            if send_email_digest(preference.user, notifications):
                count += 1
    
    return count