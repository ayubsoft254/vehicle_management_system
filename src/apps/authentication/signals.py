"""
Authentication Signals
Auto-create user profile and handle user-related events
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from .models import User, UserProfile
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create UserProfile when User is created
    Also create Client profile if user role is CLIENT
    """
    if created:
        try:
            UserProfile.objects.create(user=instance)
            logger.info(f"Profile created for user: {instance.email}")
            
            # Create Client profile if role is CLIENT
            from utils.constants import UserRole
            if instance.role == UserRole.CLIENT:
                from apps.clients.models import Client
                import uuid
                
                # Generate a unique temporary ID number using UUID
                temp_id = f'CLIENT-{str(uuid.uuid4())[:8].upper()}'
                
                # Create client profile with basic info from user
                Client.objects.create(
                    user=instance,
                    first_name=instance.first_name or 'New',
                    last_name=instance.last_name or 'Client',
                    email=instance.email,
                    id_number=temp_id,  # Unique temporary ID, should be updated by admin
                    phone_primary=instance.phone or '+254700000000',  # Use user phone or temporary
                    physical_address='To be updated'  # Should be updated by admin
                )
                logger.info(f"Client profile created for user: {instance.email} with ID: {temp_id}")
        except Exception as e:
            logger.error(f"Error creating profile for user {instance.email}: {str(e)}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure UserProfile exists and is saved when User is saved
    Also sync User data to Client profile if user has CLIENT role
    """
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            # Create profile if it doesn't exist
            UserProfile.objects.create(user=instance)
            logger.info(f"Profile created for existing user: {instance.email}")
    except Exception as e:
        logger.error(f"Error saving profile for user {instance.email}: {str(e)}")
    
    # Sync User information to Client profile if role is CLIENT
    from utils.constants import UserRole
    if instance.role == UserRole.CLIENT:
        try:
            from apps.clients.models import Client
            
            # Check if client profile exists
            if hasattr(instance, 'client_profile') and instance.client_profile:
                client = instance.client_profile
                
                # Update client profile with user information
                updated = False
                
                # Update first_name if it's different and not empty
                if instance.first_name and client.first_name != instance.first_name:
                    # Only update if current value is placeholder or different
                    if client.first_name in ['New', 'Client', ''] or client.first_name != instance.first_name:
                        client.first_name = instance.first_name
                        updated = True
                
                # Update last_name if it's different and not empty
                if instance.last_name and client.last_name != instance.last_name:
                    if client.last_name in ['New', 'Client', ''] or client.last_name != instance.last_name:
                        client.last_name = instance.last_name
                        updated = True
                
                # Update email if it's different
                if instance.email and client.email != instance.email:
                    client.email = instance.email
                    updated = True
                
                # Update phone if it's different and not empty
                if instance.phone and client.phone_primary != instance.phone:
                    # Only update if current value is placeholder or different
                    if client.phone_primary in ['+254700000000', ''] or client.phone_primary != instance.phone:
                        client.phone_primary = instance.phone
                        updated = True
                
                if updated:
                    client.save()
                    logger.info(f"Client profile synced for user: {instance.email}")
        except Exception as e:
            logger.error(f"Error syncing client profile for user {instance.email}: {str(e)}")


@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    """
    Actions to perform before saving a user
    """
    # Normalize email to lowercase
    if instance.email:
        instance.email = instance.email.lower().strip()
    
    # Log user updates
    if instance.pk:  # Existing user being updated
        try:
            old_user = User.objects.get(pk=instance.pk)
            
            # Log role changes
            if old_user.role != instance.role:
                logger.info(f"User {instance.email} role changed from {old_user.role} to {instance.role}")
                
                # If role changed TO CLIENT, create Client profile if it doesn't exist
                from utils.constants import UserRole
                if instance.role == UserRole.CLIENT:
                    from apps.clients.models import Client
                    if not hasattr(instance, 'client_profile') or not instance.client_profile:
                        import uuid
                        temp_id = f'CLIENT-{str(uuid.uuid4())[:8].upper()}'
                        Client.objects.create(
                            user=instance,
                            first_name=instance.first_name or 'New',
                            last_name=instance.last_name or 'Client',
                            email=instance.email,
                            id_number=temp_id,
                            phone_primary=instance.phone or '+254700000000',
                            physical_address='To be updated'
                        )
                        logger.info(f"Client profile created for existing user: {instance.email}")
            
            # Log status changes
            if old_user.is_active != instance.is_active:
                status = "activated" if instance.is_active else "deactivated"
                logger.info(f"User {instance.email} has been {status}")
        except User.DoesNotExist:
            pass


@receiver(post_delete, sender=User)
def user_post_delete(sender, instance, **kwargs):
    """
    Actions to perform after deleting a user
    """
    logger.info(f"User deleted: {instance.email} ({instance.get_full_name()})")
    
    # Clean up profile picture if exists
    if instance.profile_picture:
        try:
            instance.profile_picture.delete(save=False)
        except Exception as e:
            logger.error(f"Error deleting profile picture for {instance.email}: {str(e)}")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log when a user successfully logs in
    Also ensures proper redirect based on user role
    """
    from utils.constants import UserRole
    
    # Get IP address
    ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
    
    logger.info(f"User logged in: {user.email} (Role: {user.role}) from IP: {ip_address}")
    
    # Log the redirect destination for debugging
    if user.role == UserRole.CLIENT:
        logger.info(f"CLIENT user {user.email} should redirect to /clients/portal/")
    else:
        logger.info(f"User {user.email} with role {user.role} should redirect to /dashboard/")
    
    # You can add additional logic here:
    # - Update last_login timestamp (Django does this automatically)
    # - Send login notification email/SMS
    # - Track login analytics
    # - Check for suspicious login patterns


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log when a user logs out
    """
    if user:
        logger.info(f"User logged out: {user.email}")


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """
    Log failed login attempts
    """
    email = credentials.get('email', credentials.get('username', 'Unknown'))
    ip_address = request.META.get('REMOTE_ADDR', 'Unknown') if request else 'Unknown'
    
    logger.warning(f"Failed login attempt for: {email} from IP: {ip_address}")
    
    # You can add additional security measures here:
    # - Track failed login attempts per IP/email
    # - Implement rate limiting
    # - Send security alerts for multiple failed attempts
    # - Temporarily lock accounts after X failed attempts


# Additional custom signals (optional)

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Send welcome email to new users
    Disable this in production if using allauth email confirmation
    """
    if created and not instance.is_superuser:
        try:
            # Import here to avoid circular imports
            from apps.notifications.tasks import send_email_notification
            
            # Only send if email notifications are enabled in profile
            if hasattr(instance, 'profile') and instance.profile.email_notifications:
                # Queue email sending task
                # send_email_notification.delay(
                #     user_id=instance.id,
                #     subject='Welcome to Vehicle Sales Management System',
                #     template='emails/welcome.html'
                # )
                logger.info(f"Welcome email queued for: {instance.email}")
        except ImportError:
            # Notification app not yet available
            pass
        except Exception as e:
            logger.error(f"Error sending welcome email to {instance.email}: {str(e)}")


@receiver(post_save, sender=User)
def notify_admin_new_user(sender, instance, created, **kwargs):
    """
    Notify admins when a new user registers
    """
    if created and not instance.is_superuser:
        try:
            # Get all admin users
            admin_users = User.objects.filter(role='admin', is_active=True)
            
            logger.info(f"New user registered: {instance.email} - Notifying {admin_users.count()} admins")
            
            # Send notification to admins
            # This can be implemented when notification system is ready
        except Exception as e:
            logger.error(f"Error notifying admins of new user {instance.email}: {str(e)}")


# Signal for tracking user activity (optional)
@receiver(post_save, sender=User)
def track_user_changes(sender, instance, created, **kwargs):
    """
    Track user changes for audit purposes
    This integrates with the audit app when available
    """
    if not created:  # Only for updates, not creation
        try:
            # This will be used with the audit app
            # from apps.audit.models import AuditLog
            # AuditLog.objects.create(
            #     user=instance,
            #     action='update',
            #     model_name='User',
            #     object_id=instance.id,
            #     description=f"User profile updated: {instance.email}"
            # )
            pass
        except Exception as e:
            logger.error(f"Error tracking user changes for {instance.email}: {str(e)}")