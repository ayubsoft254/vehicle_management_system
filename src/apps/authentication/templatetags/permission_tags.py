"""
Custom template tags for permission checking
"""
from django import template

register = template.Library()


@register.filter(name='can_access')
def can_access_module(user, module_name):
    """
    Template filter to check if user can access a module
    Usage: {% if user|can_access:'dashboard' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        return user.can_access_module(module_name)
    except:
        return False


@register.simple_tag
def user_can_access(user, module_name):
    """
    Template tag to check if user can access a module
    Usage: {% user_can_access user 'dashboard' as can_access_dashboard %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        return user.can_access_module(module_name)
    except:
        return False


@register.filter(name='has_role')
def has_role(user, role):
    """
    Template filter to check if user has a specific role
    Usage: {% if user|has_role:'admin' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    return user.role == role
