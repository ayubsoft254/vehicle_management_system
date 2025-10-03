"""
Authentication Forms
Complete form definitions for user management
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from allauth.account.forms import SignupForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Field
from .models import User, UserProfile
from utils.constants import UserRole


class CustomSignupForm(SignupForm):
    """
    Custom signup form for django-allauth
    Adds first_name and last_name fields to the registration
    """
    first_name = forms.CharField(
        max_length=150,
        label='First Name',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your first name',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        label='Last Name',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your last name',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'placeholder': '+254712345678 or 0712345678',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        }),
        help_text='Format: +254712345678 or 0712345678'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add Tailwind CSS classes to existing fields
        self.fields['email'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your email address'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm your password'
        })
    
    def save(self, request):
        """
        Save the user with additional fields
        """
        user = super().save(request)
        
        # Set additional fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        
        # Set default role for new signups
        if not user.role:
            user.role = UserRole.CLERK  # Default role for self-registered users
        
        user.save()
        return user


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users
    Includes all necessary fields for user registration
    """
    
    class Meta:
        model = User
        fields = (
            'email', 'first_name', 'last_name', 'phone',
            'role', 'employee_id', 'department', 'hire_date',
            'address', 'city', 'profile_picture'
        )
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'email': 'Email will be used for login',
            'phone': 'Format: +254712345678 or 0712345678',
            'role': 'User role determines system permissions',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'space-y-4'
        
        # Add Tailwind CSS classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
                })
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                })
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({
                    'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
                })
            else:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                })
        
        # Crispy Forms layout
        self.helper.layout = Layout(
            Row(
                Column('email', css_class='w-full md:w-1/2'),
                Column('phone', css_class='w-full md:w-1/2'),
            ),
            Row(
                Column('first_name', css_class='w-full md:w-1/2'),
                Column('last_name', css_class='w-full md:w-1/2'),
            ),
            Row(
                Column('password1', css_class='w-full md:w-1/2'),
                Column('password2', css_class='w-full md:w-1/2'),
            ),
            Row(
                Column('role', css_class='w-full md:w-1/3'),
                Column('employee_id', css_class='w-full md:w-1/3'),
                Column('hire_date', css_class='w-full md:w-1/3'),
            ),
            Row(
                Column('department', css_class='w-full md:w-1/2'),
                Column('city', css_class='w-full md:w-1/2'),
            ),
            'address',
            'profile_picture',
            Submit('submit', 'Create User', css_class='w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 font-semibold')
        )
    
    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('This email address is already registered.')
        return email
    
    def clean_employee_id(self):
        """Validate employee ID is unique if provided"""
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id and User.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError('This employee ID is already in use.')
        return employee_id


class CustomUserChangeForm(UserChangeForm):
    """
    Form for updating existing users
    Excludes password field - use separate password change form
    """
    
    password = None  # Remove password field from change form
    
    class Meta:
        model = User
        fields = (
            'email', 'first_name', 'last_name', 'phone',
            'role', 'employee_id', 'department', 'hire_date',
            'address', 'city', 'profile_picture', 'is_active'
        )
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'space-y-4'
        
        # Add Tailwind CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
                })
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                })
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({
                    'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
                })
            else:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                })
    
    def clean_email(self):
        """Validate email is unique (excluding current user)"""
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            users = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if users.exists():
                raise forms.ValidationError('This email address is already registered.')
        return email
    
    def clean_employee_id(self):
        """Validate employee ID is unique if provided (excluding current user)"""
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            users = User.objects.filter(employee_id=employee_id).exclude(pk=self.instance.pk)
            if users.exists():
                raise forms.ValidationError('This employee ID is already in use.')
        return employee_id


class UserProfileForm(forms.ModelForm):
    """
    Form for updating user profile information
    Extended information beyond basic user data
    """
    
    class Meta:
        model = UserProfile
        fields = (
            'bio', 'date_of_birth', 'national_id',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship',
            'email_notifications', 'sms_notifications'
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about yourself...'}),
            'national_id': forms.TextInput(attrs={'placeholder': 'Enter your national ID number'}),
            'emergency_contact_name': forms.TextInput(attrs={'placeholder': 'Full name'}),
            'emergency_contact_phone': forms.TextInput(attrs={'placeholder': '+254712345678'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'placeholder': 'e.g., Spouse, Parent, Sibling'}),
        }
        help_texts = {
            'national_id': 'Your national ID or passport number',
            'emergency_contact_phone': 'Phone number of emergency contact',
        }
        labels = {
            'bio': 'Biography',
            'date_of_birth': 'Date of Birth',
            'national_id': 'National ID / Passport',
            'emergency_contact_name': 'Emergency Contact Name',
            'emergency_contact_phone': 'Emergency Contact Phone',
            'emergency_contact_relationship': 'Relationship',
            'email_notifications': 'Receive Email Notifications',
            'sms_notifications': 'Receive SMS Notifications',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'space-y-4'
        
        # Add Tailwind CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
                })
            else:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                })


class UserSearchForm(forms.Form):
    """
    Form for searching and filtering users
    Used in user list view
    """
    
    search = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, email, phone, or employee ID...',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    role = forms.ChoiceField(
        required=False,
        label='Role',
        choices=[('', 'All Roles')] + UserRole.CHOICES,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        label='Status',
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'grid grid-cols-1 md:grid-cols-4 gap-4'
        self.helper.form_show_labels = False


class UserPasswordResetForm(forms.Form):
    """
    Form for admin to reset user password
    """
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter new password'
        }),
        help_text='Password must be at least 8 characters long'
    )
    
    new_password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm new password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long")
        
        return cleaned_data