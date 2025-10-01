"""
Audit Middleware
Automatically logs all requests and user actions
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditLog, LoginHistory
from utils.constants import AuditAction
import json
import logging

logger = logging.getLogger(__name__)


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log user actions
    Captures all requests and creates audit log entries
    """
    
    # URLs to exclude from logging (to avoid too much noise)
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/admin/jsi18n/',
        '/__debug__/',
    ]
    
    # Methods to log (exclude OPTIONS, HEAD for performance)
    LOGGED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    
    # Safe paths that don't need logging (read-only views)
    SAFE_PATHS = [
        '/audit/stats/',  # AJAX endpoint
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Log the request after response (so we have status code)
        self.log_request(request, response)
        
        return response
    
    def should_log_request(self, request):
        """Determine if request should be logged"""
        
        # Skip excluded paths
        for excluded in self.EXCLUDED_PATHS:
            if request.path.startswith(excluded):
                return False
        
        # Only log specific HTTP methods
        if request.method not in self.LOGGED_METHODS:
            return False
        
        # Skip safe paths for GET requests (to reduce noise)
        if request.method == 'GET':
            for safe_path in self.SAFE_PATHS:
                if request.path.startswith(safe_path):
                    return False
        
        # Only log authenticated users (optional - remove to log anonymous)
        if not request.user.is_authenticated:
            return False
        
        return True
    
    def log_request(self, request, response):
        """Log the request to audit log"""
        
        if not self.should_log_request(request):
            return
        
        try:
            # Determine action type based on request method
            action = self.get_action_from_method(request.method)
            
            # Build description
            description = self.build_description(request)
            
            # Get IP address
            ip_address = self.get_client_ip(request)
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length
            
            # Extract model info if available
            model_name, object_id = self.extract_model_info(request)
            
            # Get request data (for POST/PUT/PATCH)
            additional_data = {}
            if request.method in ['POST', 'PUT', 'PATCH']:
                additional_data = self.get_request_data(request)
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=action,
                description=description,
                model_name=model_name,
                object_id=object_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request.path,
                request_method=request.method,
                additional_data=additional_data if additional_data else None,
            )
            
        except Exception as e:
            # Don't let logging errors break the application
            logger.error(f"Error logging audit entry: {str(e)}")
    
    def get_action_from_method(self, method):
        """Map HTTP method to audit action"""
        method_map = {
            'GET': AuditAction.READ,
            'POST': AuditAction.CREATE,
            'PUT': AuditAction.UPDATE,
            'PATCH': AuditAction.UPDATE,
            'DELETE': AuditAction.DELETE,
        }
        return method_map.get(method, AuditAction.READ)
    
    def build_description(self, request):
        """Build human-readable description of the action"""
        user = request.user.get_full_name() if request.user.is_authenticated else 'Anonymous'
        method = request.method
        path = request.path
        
        # Try to make it more readable
        if 'create' in path.lower():
            return f"{user} created a new record via {path}"
        elif 'edit' in path.lower() or 'update' in path.lower():
            return f"{user} updated a record via {path}"
        elif 'delete' in path.lower():
            return f"{user} deleted a record via {path}"
        elif method == 'GET':
            return f"{user} viewed {path}"
        elif method == 'POST':
            return f"{user} submitted form at {path}"
        else:
            return f"{user} performed {method} on {path}"
    
    def get_client_ip(self, request):
        """Get client IP address (handles proxies)"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def extract_model_info(self, request):
        """Try to extract model name and object ID from URL"""
        model_name = None
        object_id = None
        
        # Parse URL to extract model info
        path_parts = request.path.strip('/').split('/')
        
        # Common patterns: /app/model/id/ or /app/model/id/action/
        if len(path_parts) >= 2:
            # Try to get model name from path
            if path_parts[0] in ['vehicles', 'clients', 'payments', 'users', 
                                  'expenses', 'auctions', 'repossessions']:
                model_name = path_parts[0].rstrip('s').capitalize()  # vehicles -> Vehicle
                
                # Try to get object ID
                if len(path_parts) >= 2 and path_parts[1].isdigit():
                    object_id = path_parts[1]
        
        return model_name, object_id
    
    def get_request_data(self, request):
        """Extract relevant data from POST/PUT/PATCH requests"""
        data = {}
        
        try:
            # Get POST data (excluding sensitive fields)
            if hasattr(request, 'POST'):
                for key, value in request.POST.items():
                    # Skip sensitive fields
                    if key.lower() in ['password', 'password1', 'password2', 
                                       'csrfmiddlewaretoken', 'api_key', 'token']:
                        continue
                    
                    # Limit value length
                    if isinstance(value, str) and len(value) > 200:
                        value = value[:200] + '...'
                    
                    data[key] = value
        except Exception as e:
            logger.error(f"Error extracting request data: {str(e)}")
        
        return data


# Signal receivers for login/logout tracking

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login"""
    try:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Create audit log
        AuditLog.log_login(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request.path,
            request_method=request.method,
        )
        
        # Create login history entry
        LoginHistory.objects.create(
            user=user,
            email_attempted=user.email,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=request.session.session_key,
        )
        
    except Exception as e:
        logger.error(f"Error logging user login: {str(e)}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout"""
    try:
        if user:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            
            # Create audit log
            AuditLog.log_logout(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request.path,
                request_method=request.method,
            )
            
            # Update login history with logout time
            try:
                login_entry = LoginHistory.objects.filter(
                    user=user,
                    session_key=request.session.session_key,
                    logout_time__isnull=True
                ).latest('timestamp')
                
                login_entry.logout_time = timezone.now()
                login_entry.save()
            except LoginHistory.DoesNotExist:
                pass
            
    except Exception as e:
        logger.error(f"Error logging user logout: {str(e)}")


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempt"""
    try:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        email = credentials.get('email', credentials.get('username', 'unknown'))
        
        # Create login history entry for failed attempt
        LoginHistory.objects.create(
            email_attempted=email,
            success=False,
            failure_reason='Invalid credentials',
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Also log in audit log
        AuditLog.objects.create(
            user=None,
            action=AuditAction.LOGIN,
            description=f"Failed login attempt for {email}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request.path,
            request_method=request.method,
            additional_data={'email': email, 'status': 'failed'}
        )
        
    except Exception as e:
        logger.error(f"Error logging failed login: {str(e)}")


# Helper function for getting IP
def get_client_ip(request):
    """Get client IP address (handles proxies)"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Import timezone here to avoid circular import
from django.utils import timezone