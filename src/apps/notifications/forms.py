"""
Notifications App - Forms
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    NotificationSchedule
)

User = get_user_model()


# ============================================================================
# NOTIFICATION FORMS
# ============================================================================

class NotificationForm(forms.ModelForm):
    """Form for creating manual notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'user',
            'title',
            'message',
            'notification_type',
            'priority',
            'action_text',
            'action_url',
            'expires_at',
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Notification title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notification message...'
            }),
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'action_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., View Details'
            }),
            'action_url': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL for action button'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
    
    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError('Expiration date must be in the future.')
        return expires_at


class BulkNotificationForm(forms.Form):
    """Form for sending notifications to multiple users"""
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Notification title'
        })
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Notification message...'
        })
    )
    notification_type = forms.ChoiceField(
        choices=Notification.NOTIFICATION_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        choices=Notification.PRIORITY_CHOICES,
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sms = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class NotificationFilterForm(forms.Form):
    """Form for filtering notifications"""
    
    notification_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + list(Notification.NOTIFICATION_TYPE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All Priorities')] + list(Notification.PRIORITY_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_read = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('true', 'Read'), ('false', 'Unread')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


# ============================================================================
# NOTIFICATION PREFERENCE FORMS
# ============================================================================

class NotificationPreferenceForm(forms.ModelForm):
    """Form for managing notification preferences"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'enabled',
            'in_app_enabled',
            'email_enabled',
            'email_address',
            'email_digest',
            'email_digest_time',
            'sms_enabled',
            'phone_number',
            'push_enabled',
            'notify_payment',
            'notify_vehicle',
            'notify_auction',
            'notify_document',
            'notify_insurance',
            'notify_repossession',
            'notify_expense',
            'notify_payroll',
            'notify_system',
            'notify_urgent_only',
            'notify_high_and_urgent',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
        ]
        widgets = {
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'in_app_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_address': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Override default email'
            }),
            'email_digest': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_digest_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'sms_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'push_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_vehicle': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_auction': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_document': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_insurance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_repossession': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_expense': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_payroll': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_system': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_urgent_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_high_and_urgent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_start': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate quiet hours
        quiet_enabled = cleaned_data.get('quiet_hours_enabled')
        quiet_start = cleaned_data.get('quiet_hours_start')
        quiet_end = cleaned_data.get('quiet_hours_end')
        
        if quiet_enabled and (not quiet_start or not quiet_end):
            raise ValidationError('Quiet hours start and end times are required when enabled.')
        
        # Validate email address if email enabled
        email_enabled = cleaned_data.get('email_enabled')
        email_address = cleaned_data.get('email_address')
        
        if email_enabled and not email_address and not self.instance.user.email:
            raise ValidationError('Email address is required when email notifications are enabled.')
        
        # Validate phone number if SMS enabled
        sms_enabled = cleaned_data.get('sms_enabled')
        phone_number = cleaned_data.get('phone_number')
        
        if sms_enabled and not phone_number:
            raise ValidationError('Phone number is required when SMS notifications are enabled.')
        
        # Validate priority filters
        urgent_only = cleaned_data.get('notify_urgent_only')
        high_and_urgent = cleaned_data.get('notify_high_and_urgent')
        
        if urgent_only and high_and_urgent:
            raise ValidationError('Cannot select both urgent only and high/urgent filters.')
        
        return cleaned_data


class QuickPreferenceForm(forms.Form):
    """Quick toggle form for notification preferences"""
    
    email_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    sms_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    push_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# ============================================================================
# NOTIFICATION TEMPLATE FORMS
# ============================================================================

class NotificationTemplateForm(forms.ModelForm):
    """Form for creating/editing notification templates"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'name',
            'description',
            'template_type',
            'notification_type',
            'title_template',
            'message_template',
            'subject_template',
            'html_template',
            'priority',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Template name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Template description...'
            }),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'title_template': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Hello {{ user.first_name }}'
            }),
            'message_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Use {{ variable }} for dynamic content'
            }),
            'subject_template': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email subject (for email templates)'
            }),
            'html_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'HTML email template (optional)'
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Check for duplicate names
        qs = NotificationTemplate.objects.filter(name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError('A template with this name already exists.')
        
        return name


class TemplateTestForm(forms.Form):
    """Form for testing notification templates"""
    
    template = forms.ModelChoiceField(
        queryset=NotificationTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    test_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='User to send test notification to'
    )
    context_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': '{"variable": "value"}'
        }),
        help_text='JSON context for template variables'
    )


# ============================================================================
# NOTIFICATION SCHEDULE FORMS
# ============================================================================

class NotificationScheduleForm(forms.ModelForm):
    """Form for creating/editing notification schedules"""
    
    class Meta:
        model = NotificationSchedule
        fields = [
            'name',
            'description',
            'template',
            'title',
            'message',
            'notification_type',
            'users',
            'frequency',
            'scheduled_time',
            'status',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Schedule name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Schedule description...'
            }),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Manual notification title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Manual notification message...'
            }),
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'users': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '10'
            }),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        template = cleaned_data.get('template')
        title = cleaned_data.get('title')
        message = cleaned_data.get('message')
        
        # Either template or manual content required
        if not template and not (title and message):
            raise ValidationError(
                'Either select a template or provide manual title and message.'
            )
        
        # Validate scheduled time
        scheduled_time = cleaned_data.get('scheduled_time')
        if scheduled_time and scheduled_time <= timezone.now():
            raise ValidationError('Scheduled time must be in the future.')
        
        return cleaned_data


class QuickScheduleForm(forms.Form):
    """Quick form for scheduling a notification"""
    
    template = forms.ModelChoiceField(
        queryset=NotificationTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '5'
        })
    )
    scheduled_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )


# ============================================================================
# UTILITY FORMS
# ============================================================================

class MarkAsReadForm(forms.Form):
    """Form for marking notifications as read"""
    
    notification_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_notification_ids(self):
        ids = self.cleaned_data.get('notification_ids')
        if ids:
            return [id.strip() for id in ids.split(',')]
        return []


class NotificationSearchForm(forms.Form):
    """Form for searching notifications"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search notifications...'
        })
    )
    notification_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + list(Notification.NOTIFICATION_TYPE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All Priorities')] + list(Notification.PRIORITY_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    unread_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class NotificationActionForm(forms.Form):
    """Form for batch notification actions"""
    
    ACTION_CHOICES = [
        ('mark_read', 'Mark as Read'),
        ('mark_unread', 'Mark as Unread'),
        ('dismiss', 'Dismiss'),
        ('delete', 'Delete'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notification_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_notification_ids(self):
        ids = self.cleaned_data.get('notification_ids')
        if ids:
            return [id.strip() for id in ids.split(',')]
        return []