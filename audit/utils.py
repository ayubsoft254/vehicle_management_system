from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import AuditLog, LoginAttempt, UserSession, SystemEvent, DataExport


class AuditLogger:
    """Utility class for logging audit events"""
    
    @staticmethod
    def log_action(user, action_type, description, **kwargs):
        """
        Log a user action
        
        Args:
            user: User instance or None
            action_type: One of the ACTION_CHOICES
            description: Human readable description
            **kwargs: Additional audit log fields
        """
        try:
            audit_log = AuditLog.objects.create(
                user=user,
                action_type=action_type,
                description=description,
                module_name=kwargs.get('module_name', 'Unknown'),
                severity=kwargs.get('severity', 'LOW'),
                content_type=kwargs.get('content_type'),
                object_id=kwargs.get('object_id'),
                table_name=kwargs.get('table_name'),
                record_id=kwargs.get('record_id'),
                ip_address=kwargs.get('ip_address'),
                user_agent=kwargs.get('user_agent'),
                request_method=kwargs.get('request_method'),
                request_url=kwargs.get('request_url'),
                old_values=kwargs.get('old_values'),
                new_values=kwargs.get('new_values'),
                changed_fields=kwargs.get('changed_fields'),
                session_key=kwargs.get('session_key'),
                is_successful=kwargs.get('is_successful', True),
                error_message=kwargs.get('error_message'),
                is_sensitive=kwargs.get('is_sensitive', False),
            )
            return audit_log
        except Exception as e:
            # Log the error but don't raise to avoid breaking the main operation
            print(f"Audit logging error: {e}")
            return None
    
    @staticmethod
    def log_model_change(user, instance, action_type, old_values=None, **kwargs):
        """
        Log changes to a model instance
        
        Args:
            user: User instance
            instance: Model instance being changed
            action_type: CREATE, UPDATE, DELETE
            old_values: Dict of old field values (for UPDATE)
            **kwargs: Additional context
        """
        content_type = ContentType.objects.get_for_model(instance)
        
        # For updates, calculate changed fields
        changed_fields = []
        new_values = {}
        
        if action_type == 'UPDATE' and old_values:
            for field in instance._meta.fields:
                field_name = field.name
                old_val = old_values.get(field_name)
                new_val = getattr(instance, field_name, None)
                
                if old_val != new_val:
                    changed_fields.append(field_name)
                    new_values[field_name] = str(new_val) if new_val is not None else None
        
        description = f"{action_type} {content_type.model} (ID: {instance.pk})"
        
        return AuditLogger.log_action(
            user=user,
            action_type=action_type,
            description=description,
            content_type=content_type,
            object_id=instance.pk,
            table_name=content_type.model,
            record_id=str(instance.pk),
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            **kwargs
        )
    
    @staticmethod
    def log_login_attempt(username, ip_address, user_agent, is_successful, user=None, failure_reason=None):
        """Log login attempt"""
        try:
            return LoginAttempt.objects.create(
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                is_successful=is_successful,
                failure_reason=failure_reason,
                user=user
            )
        except Exception as e:
            print(f"Login attempt logging error: {e}")
            return None
    
    @staticmethod
    def log_user_session(user, session_key, ip_address, user_agent):
        """Log user session start"""
        try:
            # End any existing active sessions for this user
            UserSession.objects.filter(user=user, is_active=True).update(
                is_active=False,
                logout_time=timezone.now()
            )
            
            return UserSession.objects.create(
                user=user,
                session_key=session_key,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"User session logging error: {e}")
            return None
    
    @staticmethod
    def log_system_event(event_type, description, **kwargs):
        """Log system event"""
        try:
            return SystemEvent.objects.create(
                event_type=event_type,
                description=description,
                details=kwargs.get('details'),
                severity=kwargs.get('severity', 'LOW')
            )
        except Exception as e:
            print(f"System event logging error: {e}")
            return None
    
    @staticmethod
    def log_data_export(user, export_type, module_name, description, **kwargs):
        """Log data export"""
        try:
            return DataExport.objects.create(
                user=user,
                export_type=export_type,
                module_name=module_name,
                description=description,
                file_name=kwargs.get('file_name'),
                file_size=kwargs.get('file_size'),
                record_count=kwargs.get('record_count'),
                filters_applied=kwargs.get('filters_applied'),
                ip_address=kwargs.get('ip_address')
            )
        except Exception as e:
            print(f"Data export logging error: {e}")
            return None


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


# audit/middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user
from .utils import AuditLogger, get_client_ip, get_user_agent
import json


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log user actions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Store request start time and details"""
        request._audit_start_time = timezone.now()
        request._audit_ip = get_client_ip(request)
        request._audit_user_agent = get_user_agent(request)
    
    def process_response(self, request, response):
        """Log the request after processing"""
        user = getattr(request, 'user', None)
        
        # Skip logging for certain paths
        skip_paths = ['/admin/jsi18n/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in skip_paths):
            return response
        
        # Skip non-authenticated users for most actions (except login)
        if not user or not user.is_authenticated:
            if not request.path.startswith('/login/'):
                return response
        
        # Determine action type based on method
        action_map = {
            'GET': 'VIEW',
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE'
        }
        
        action_type = action_map.get(request.method, 'VIEW')
        
        # Create description
        description = f"{request.method} {request.path}"
        if hasattr(response, 'status_code'):
            description += f" (Status: {response.status_code})"
        
        # Determine module name from URL
        module_name = self._get_module_name(request.path)
        
        # Log the action
        AuditLogger.log_action(
            user=user if user and user.is_authenticated else None,
            action_type=action_type,
            description=description,
            module_name=module_name,
            ip_address=request._audit_ip,
            user_agent=request._audit_user_agent,
            request_method=request.method,
            request_url=request.build_absolute_uri(),
            session_key=request.session.session_key,
            is_successful=response.status_code < 400,
            error_message=None if response.status_code < 400 else f"HTTP {response.status_code}"
        )
        
        return response
    
    def _get_module_name(self, path):
        """Extract module name from URL path"""
        module_map = {
            '/vehicles/': 'Vehicle Inventory',
            '/clients/': 'Client Management',
            '/payments/': 'Payment Module',
            '/payroll/': 'Payroll Management',
            '/expenses/': 'Expense Tracking',
            '/repossessed/': 'Repossessed Cars',
            '/auctions/': 'Auction Management',
            '/insurance/': 'Insurance Management',
            '/documents/': 'Document Manager',
            '/reports/': 'Reporting Module',
            '/audit/': 'Audit Logs',
            '/admin/': 'Administration',
            '/login/': 'Authentication',
            '/logout/': 'Authentication',
        }
        
        for path_prefix, module in module_map.items():
            if path.startswith(path_prefix):
                return module
        
        return 'Unknown Module'