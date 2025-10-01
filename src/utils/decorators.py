"""
Custom Decorators for Access Control and Utilities
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from apps.permissions.models import RolePermission
from utils.constants import AccessLevel


def role_required(*roles):
    """
    Decorator to restrict access to specific roles
    Usage: @role_required('admin', 'manager')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('account_login')
            
            if request.user.role in roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
        
        return wrapper
    return decorator


def module_permission_required(module_name, min_access_level=AccessLevel.READ_ONLY):
    """
    Decorator to check module-level permissions
    Usage: @module_permission_required('vehicles', AccessLevel.READ_WRITE)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('account_login')
            
            # Superusers have full access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check role permission
            try:
                permission = RolePermission.objects.get(
                    role=request.user.role,
                    module_name=module_name
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
                
                if user_level >= required_level:
                    return view_func(request, *args, **kwargs)
                
            except RolePermission.DoesNotExist:
                pass
            
            messages.error(request, f'You do not have sufficient permissions to access this module.')
            return redirect('dashboard:home')
        
        return wrapper
    return decorator


def ajax_required(view_func):
    """
    Decorator to ensure request is AJAX
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            raise PermissionDenied('This endpoint only accepts AJAX requests.')
        return view_func(request, *args, **kwargs)
    
    return wrapper


def superuser_required(view_func):
    """
    Decorator to restrict access to superusers only
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('account_login')
        
        if not request.user.is_superuser:
            messages.error(request, 'Only administrators can access this page.')
            return redirect('dashboard:home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper