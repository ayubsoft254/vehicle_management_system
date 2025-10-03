"""
Audit Utility Functions
Helper functions for audit logging throughout the application
"""
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog


def log_audit(user, action, model_name, description, **kwargs):
    """
    Simple utility function to log audit actions
    
    Args:
        user: User instance who performed the action
        action: Action type (create, read, update, delete, etc.)
        model_name: Name of the model being acted upon
        description: Human-readable description of the action
        **kwargs: Additional optional parameters like ip_address, user_agent, etc.
    
    Returns:
        AuditLog instance
    """
    return AuditLog.objects.log_action(
        user=user,
        action=action,
        description=description,
        model_name=model_name,
        **kwargs
    )


def log_audit_with_object(user, action, obj, description=None, changes=None, **kwargs):
    """
    Log audit action with a specific object instance
    
    Args:
        user: User instance who performed the action
        action: Action type (create, read, update, delete, etc.)
        obj: Model instance being acted upon
        description: Optional description (will be auto-generated if not provided)
        changes: Dictionary of changes (for update actions)
        **kwargs: Additional optional parameters
    
    Returns:
        AuditLog instance
    """
    if not description:
        description = f"{action.title()} {obj.__class__.__name__}: {obj}"
    
    return AuditLog.objects.log_action(
        user=user,
        action=action,
        description=description,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk),
        changes=changes,
        **kwargs
    )


def get_user_activity(user, days=30):
    """
    Get recent activity for a specific user
    
    Args:
        user: User instance
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet of AuditLog entries
    """
    return AuditLog.objects.user_activity(user)[:100]  # Limit to last 100 entries


def get_model_activity(model_name, days=30):
    """
    Get recent activity for a specific model
    
    Args:
        model_name: Name of the model
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet of AuditLog entries
    """
    return AuditLog.objects.by_model(model_name)


def get_recent_activity(days=7):
    """
    Get recent system-wide activity
    
    Args:
        days: Number of days to look back (default: 7)
    
    Returns:
        QuerySet of AuditLog entries
    """
    return AuditLog.objects.recent_activity(days)
