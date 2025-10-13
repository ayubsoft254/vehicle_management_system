"""
Custom Allauth Adapters
Customizes django-allauth behavior for our application
"""
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.contrib import messages


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter for django-allauth
    Customize signup, login, and email behavior
    """
    
    def is_open_for_signup(self, request):
        """
        Whether to allow sign ups.
        Set to True to enable public registration.
        New users will be assigned CLIENT role by default.
        """
        # Public registration is enabled
        # New users are automatically assigned CLIENT role
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Saves a new User instance using information provided in the
        signup form.
        """
        from utils.constants import UserRole
        
        # Get data from form
        data = form.cleaned_data
        
        # Set basic user information
        user.email = data.get('email')
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        
        # Always set CLIENT role for self-registration (public signup)
        # Admin-created users will have their role set during user creation
        user.role = UserRole.CLIENT
        
        # Set additional fields if they exist in the form
        if 'phone' in data:
            user.phone = data.get('phone', '')
        
        if commit:
            user.save()
        
        return user
    
    def get_login_redirect_url(self, request):
        """
        Returns the URL to redirect to after a successful login.
        Redirects based on user role:
        - CLIENT users → /clients/portal/
        - All other users → /dashboard/
        """
        from utils.constants import UserRole
        from django.urls import resolve, Resolver404
        
        # Check if there's a 'next' parameter in the request
        # Only honor 'next' if it's not the default login page
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and next_url not in ['/accounts/login/', '/accounts/signup/', '/']:
            try:
                # Verify the next URL is valid
                resolve(next_url)
                return next_url
            except Resolver404:
                pass  # Invalid URL, fall through to role-based redirect
        
        # Role-based redirect
        if request.user.is_authenticated:
            if request.user.role == UserRole.CLIENT:
                return '/clients/portal/'  # Client portal dashboard
            elif request.user.role == UserRole.AUCTIONEER:
                return '/auctions/'  # Auctioneer specific dashboard
            else:
                # All other roles (ADMIN, MANAGER, SALES, ACCOUNTANT, CLERK, etc.)
                return '/dashboard/'
        
        # Fallback to default
        return super().get_login_redirect_url(request)
    
    def get_logout_redirect_url(self, request):
        """
        Returns the URL to redirect to after logout.
        """
        return '/accounts/login/'
    
    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Constructs the email confirmation (activation) url.
        """
        url = super().get_email_confirmation_url(request, emailconfirmation)
        return url
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Override to customize confirmation email
        """
        super().send_confirmation_mail(request, emailconfirmation, signup)
    
    def confirm_email(self, request, email_address):
        """
        Marks the email address as confirmed on the db
        """
        super().confirm_email(request, email_address)
        
        # Add custom logic after email confirmation
        # For example, send a welcome email or notification
        if email_address.user:
            messages.success(
                request, 
                f'Welcome {email_address.user.get_full_name()}! Your email has been confirmed.'
            )
    
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        """
        Wrapper of `django.contrib.messages.add_message`, that
        reads the message text from a template.
        """
        # You can customize messages here
        return super().add_message(request, level, message_template, message_context, extra_tags)
    
    def ajax_response(self, request, response, redirect_to=None, form=None, data=None):
        """
        Override to customize AJAX responses
        """
        return super().ajax_response(request, response, redirect_to, form, data)
    
    def pre_login(self, request, user, *, email_verification, signal_kwargs, email, signup, redirect_url):
        """
        Called just before the user is logged in.
        """
        # Add custom logic before login
        # For example, check if user is active
        if not user.is_active:
            messages.error(request, 'Your account has been deactivated. Please contact the administrator.')
            raise Exception('User account is inactive')
        
        return super().pre_login(
            request, 
            user, 
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url
        )
    
    def authentication_failed(self, request, **kwargs):
        """
        Called when authentication fails.
        """
        # Add custom logic for failed authentication
        # For example, log failed login attempts
        pass
    
    def populate_username(self, request, user):
        """
        Fills in a valid username, if required and missing.
        Since we don't use username, this is not needed.
        """
        pass
    
    def get_user_search_fields(self):
        """
        Define which fields to search when looking up users
        """
        return ['email', 'first_name', 'last_name', 'phone']