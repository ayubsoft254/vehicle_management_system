from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import RolePermission


def role_required(allowed_roles):
    """
    Decorator to restrict access based on user roles.
    
    Usage:
        @role_required(['admin', 'manager'])
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('account_login')
            
            if request.user.role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def module_permission_required(module_name, min_access_level='view'):
    """
    Decorator to check module-level permissions based on RolePermission.
    
    Access levels hierarchy: none < view < edit < full
    
    Usage:
        @module_permission_required('vehicles', 'edit')
        def edit_vehicle(request, pk):
            ...
    """
    access_hierarchy = {
        'none': 0,
        'view': 1,
        'edit': 2,
        'full': 3,
    }
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('account_login')
            
            # Admin always has full access
            if request.user.role == 'admin':
                return view_func(request, *args, **kwargs)
            
            # Check permission
            try:
                permission = RolePermission.objects.get(
                    role=request.user.role,
                    module_name=module_name
                )
                
                user_access_level = access_hierarchy.get(permission.access_level, 0)
                required_access_level = access_hierarchy.get(min_access_level, 1)
                
                if user_access_level >= required_access_level:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, f'You need {min_access_level} access to this module.')
                    raise PermissionDenied
                    
            except RolePermission.DoesNotExist:
                messages.error(request, 'You do not have permission to access this module.')
                raise PermissionDenied
        
        return wrapper
    return decorator


def ajax_required(view_func):
    """
    Decorator to ensure the request is an AJAX request.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            raise PermissionDenied('This endpoint only accepts AJAX requests.')
        return view_func(request, *args, **kwargs)
    return wrapper