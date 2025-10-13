"""
Template tags for permission checking
"""
from django import template
from apps.permissions.models import RolePermission
from utils.constants import AccessLevel

register = template.Library()


@register.simple_tag
def has_module_permission(user, module_name, min_access_level=AccessLevel.READ_ONLY):
    """
    Check if user has permission to access a module with minimum access level
    Usage: {% has_module_permission user 'vehicles' 'read_write' as can_edit %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        
        # Define access level hierarchy
        access_hierarchy = {
            AccessLevel.NO_ACCESS: 0,
            AccessLevel.READ_ONLY: 1,
            AccessLevel.READ_WRITE: 2,
            AccessLevel.FULL_ACCESS: 3,
        }
        
        user_level = access_hierarchy.get(permission.access_level, 0)
        required_level = access_hierarchy.get(min_access_level, 0)
        
        return user_level >= required_level
    
    except RolePermission.DoesNotExist:
        return False


@register.simple_tag
def can_create(user, module_name):
    """
    Check if user can create records in a module
    Usage: {% can_create user 'vehicles' as can_create_vehicle %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        return permission.can_create
    except RolePermission.DoesNotExist:
        return False


@register.simple_tag
def can_edit(user, module_name):
    """
    Check if user can edit records in a module
    Usage: {% can_edit user 'vehicles' as can_edit_vehicle %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        return permission.can_edit
    except RolePermission.DoesNotExist:
        return False


@register.simple_tag
def can_delete(user, module_name):
    """
    Check if user can delete records in a module
    Usage: {% can_delete user 'vehicles' as can_delete_vehicle %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        return permission.can_delete
    except RolePermission.DoesNotExist:
        return False


@register.simple_tag
def can_export(user, module_name):
    """
    Check if user can export data from a module
    Usage: {% can_export user 'vehicles' as can_export_vehicles %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        return permission.can_export
    except RolePermission.DoesNotExist:
        return False


@register.filter
def has_read_write_access(user, module_name):
    """
    Filter to check if user has read-write access
    Usage: {% if user|has_read_write_access:'vehicles' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        
        access_hierarchy = {
            AccessLevel.NO_ACCESS: 0,
            AccessLevel.READ_ONLY: 1,
            AccessLevel.READ_WRITE: 2,
            AccessLevel.FULL_ACCESS: 3,
        }
        
        user_level = access_hierarchy.get(permission.access_level, 0)
        required_level = access_hierarchy.get(AccessLevel.READ_WRITE, 0)
        
        return user_level >= required_level
    
    except RolePermission.DoesNotExist:
        return False


@register.filter
def has_full_access(user, module_name):
    """
    Filter to check if user has full access
    Usage: {% if user|has_full_access:'vehicles' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        permission = RolePermission.objects.get(
            role=user.role,
            module_name=module_name,
            is_active=True
        )
        return permission.access_level == AccessLevel.FULL_ACCESS
    
    except RolePermission.DoesNotExist:
        return False
