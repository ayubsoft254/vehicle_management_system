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
        You can set this to False to disable public registration.
        Only admins can create users through the admin interface.
        """
        # Change to False if you want to disable public registration
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Saves a new User instance using information provided in the
        signup form.
        """
        # Get data from form
        data = form.cleaned_data
        
        # Set basic user information
        user.email = data.get('email')
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        
        # Set default role for new signups
        # You can customize this based on your needs
        if not user.role:
            user.role = 'clerk'  # Default role for self-registered users
        
        # Set additional fields if they exist in the form
        if 'phone' in data:
            user.phone = data.get('phone', '')
        
        if commit:
            user.save()
        
        return user
    
    def get_login_redirect_url(self, request):
        """
        Returns the URL to redirect to after a successful login.
        Can customize based on user role.
        """
        # Get the default redirect URL
        path = super().get_login_redirect_url(request)
        
        # Customize redirect based on user role
        if request.user.is_authenticated:
            if request.user.role == 'admin':
                return '/dashboard/'
            elif request.user.role == 'manager':
                return '/dashboard/'
            elif request.user.role == 'sales':
                return '/dashboard/'
            elif request.user.role == 'accountant':
                return '/dashboard/'
            elif request.user.role == 'auctioneer':
                return '/auctions/'
            else:
                return '/dashboard/'
        
        return path
    
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