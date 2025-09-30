from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from .models import RolePermission


class RolePermissionMixin(LoginRequiredMixin):
    """
    Mixin for class-based views to check role-based permissions.
    """
    allowed_roles = []  # List of allowed roles
    module_name = None  # Module name for permission check
    min_access_level = 'view'  # Minimum access level required
    
    access_hierarchy = {
        'none': 0,
        'view': 1,
        'edit': 2,
        'full': 3,
    }
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Admin always has access
        if request.user.role == 'admin':
            return super().dispatch(request, *args, **kwargs)
        
        # Check role-based access
        if self.allowed_roles and request.user.role not in self.allowed_roles:
            messages.error(request, 'You do not have permission to access this page.')
            raise PermissionDenied
        
        # Check module permission
        if self.module_name:
            if not self.check_module_permission(request.user):
                messages.error(request, f'You need {self.min_access_level} access to this module.')
                raise PermissionDenied
        
        return super().dispatch(request, *args, **kwargs)
    
    def check_module_permission(self, user):
        """
        Check if user has required module permission.
        """
        try:
            permission = RolePermission.objects.get(
                role=user.role,
                module_name=self.module_name
            )
            
            user_access_level = self.access_hierarchy.get(permission.access_level, 0)
            required_access_level = self.access_hierarchy.get(self.min_access_level, 1)
            
            return user_access_level >= required_access_level
            
        except RolePermission.DoesNotExist:
            return False


class AuditMixin:
    """
    Mixin to automatically log create/update actions.
    """
    def form_valid(self, form):
        """
        Add created_by or updated_by automatically.
        """
        if hasattr(form.instance, 'created_by') and not form.instance.pk:
            form.instance.created_by = self.request.user
        
        if hasattr(form.instance, 'updated_by'):
            form.instance.updated_by = self.request.user
        
        return super().form_valid(form)