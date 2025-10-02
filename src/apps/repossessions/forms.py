"""
Forms for the repossessions app.
Handles repossession creation, status updates, and tracking.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    Repossession, RepossessionDocument, RepossessionNote,
    RepossessionExpense, RepossessionNotice, RepossessionContact,
    RepossessionRecoveryAttempt
)

User = get_user_model()


class RepossessionForm(forms.ModelForm):
    """Form for creating and editing repossessions."""
    
    class Meta:
        model = Repossession
        fields = [
            'vehicle', 'client', 'reason', 'outstanding_amount',
            'payments_missed', 'last_payment_date', 'initiated_date',
            'assigned_to', 'last_known_location', 'notes'
        ]
        widgets = {
            'vehicle': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select vehicle'
            }),
            'client': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select client'
            }),
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'outstanding_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'payments_missed': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'last_payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'initiated_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select agent (optional)'
            }),
            'last_known_location': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Last known vehicle location'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['assigned_to'].required = False
        self.fields['last_payment_date'].required = False
        self.fields['last_known_location'].required = False
        self.fields['notes'].required = False
        
        # Filter active users only
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True)
    
    def clean_outstanding_amount(self):
        """Validate outstanding amount."""
        amount = self.cleaned_data.get('outstanding_amount')
        
        if amount and amount <= 0:
            raise ValidationError('Outstanding amount must be greater than zero.')
        
        return amount
    
    def clean_initiated_date(self):
        """Validate initiated date."""
        initiated_date = self.cleaned_data.get('initiated_date')
        
        if initiated_date and initiated_date > date.today():
            raise ValidationError('Initiated date cannot be in the future.')
        
        return initiated_date
    
    def clean(self):
        """Additional validation."""
        cleaned_data = super().clean()
        last_payment_date = cleaned_data.get('last_payment_date')
        initiated_date = cleaned_data.get('initiated_date')
        
        if last_payment_date and initiated_date:
            if last_payment_date > initiated_date:
                raise ValidationError(
                    'Last payment date cannot be after repossession initiation date.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save repossession."""
        repossession = super().save(commit=False)
        
        if self.user and not repossession.pk:
            repossession.created_by = self.user
        
        if commit:
            repossession.save()
        
        return repossession


class RepossessionStatusUpdateForm(forms.Form):
    """Form for updating repossession status."""
    
    status = forms.ChoiceField(
        choices=Repossession.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for status change'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        super().__init__(*args, **kwargs)
        
        if self.repossession:
            self.fields['status'].initial = self.repossession.status


class RepossessionDocumentForm(forms.ModelForm):
    """Form for uploading repossession documents."""
    
    class Meta:
        model = RepossessionDocument
        fields = ['document_type', 'title', 'description', 'file']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Document description (optional)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['description'].required = False
    
    def clean_file(self):
        """Validate file upload."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 10MB.')
            
            # Check file type
            allowed_types = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'image/jpeg',
                'image/png'
            ]
            
            if file.content_type not in allowed_types:
                raise ValidationError(
                    'Only PDF, Word documents, and images (JPEG, PNG) are allowed.'
                )
        
        return file
    
    def save(self, commit=True):
        """Save document with metadata."""
        document = super().save(commit=False)
        
        if self.repossession:
            document.repossession = self.repossession
        
        if self.user:
            document.uploaded_by = self.user
        
        if document.file:
            document.file_name = document.file.name
            document.file_size = document.file.size
            document.file_type = document.file.content_type
        
        if commit:
            document.save()
        
        return document


class RepossessionNoteForm(forms.ModelForm):
    """Form for adding notes to repossession."""
    
    class Meta:
        model = RepossessionNote
        fields = ['note', 'note_type', 'is_important']
        widgets = {
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter note...'
            }),
            'note_type': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select type (optional)'
            }),
            'is_important': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['note_type'].required = False
    
    def save(self, commit=True):
        """Save note."""
        note = super().save(commit=False)
        
        if self.repossession:
            note.repossession = self.repossession
        
        if self.user:
            note.created_by = self.user
        
        if commit:
            note.save()
        
        return note


class RepossessionExpenseForm(forms.ModelForm):
    """Form for recording repossession expenses."""
    
    class Meta:
        model = RepossessionExpense
        fields = [
            'expense_type', 'description', 'amount', 'expense_date',
            'vendor', 'receipt_number', 'paid', 'payment_date',
            'payment_method', 'notes'
        ]
        widgets = {
            'expense_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Expense description'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'expense_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'vendor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vendor name (optional)'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Receipt number (optional)'
            }),
            'paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_method': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Payment method'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['vendor'].required = False
        self.fields['receipt_number'].required = False
        self.fields['payment_date'].required = False
        self.fields['payment_method'].required = False
        self.fields['notes'].required = False
    
    def clean(self):
        """Validate payment details."""
        cleaned_data = super().clean()
        paid = cleaned_data.get('paid')
        payment_date = cleaned_data.get('payment_date')
        
        if paid and not payment_date:
            raise ValidationError('Payment date is required when expense is marked as paid.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save expense."""
        expense = super().save(commit=False)
        
        if self.repossession:
            expense.repossession = self.repossession
        
        if self.user:
            expense.created_by = self.user
        
        if commit:
            expense.save()
        
        return expense


class RepossessionNoticeForm(forms.ModelForm):
    """Form for sending repossession notices."""
    
    class Meta:
        model = RepossessionNotice
        fields = [
            'notice_type', 'notice_date', 'delivery_method',
            'delivery_address', 'tracking_number', 'response_deadline',
            'content'
        ]
        widgets = {
            'notice_type': forms.Select(attrs={'class': 'form-control'}),
            'notice_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'delivery_method': forms.Select(attrs={'class': 'form-control'}),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Delivery address'
            }),
            'tracking_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tracking number (if applicable)'
            }),
            'response_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Notice content/message'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['tracking_number'].required = False
        self.fields['response_deadline'].required = False
    
    def clean_response_deadline(self):
        """Validate response deadline."""
        deadline = self.cleaned_data.get('response_deadline')
        notice_date = self.cleaned_data.get('notice_date')
        
        if deadline and notice_date:
            if deadline < notice_date:
                raise ValidationError('Response deadline cannot be before notice date.')
        
        return deadline
    
    def save(self, commit=True):
        """Save notice."""
        notice = super().save(commit=False)
        
        if self.repossession:
            notice.repossession = self.repossession
        
        if self.user:
            notice.sent_by = self.user
        
        if commit:
            notice.save()
        
        return notice


class RepossessionContactForm(forms.ModelForm):
    """Form for recording client contacts."""
    
    class Meta:
        model = RepossessionContact
        fields = [
            'contact_date', 'contact_method', 'contacted_person',
            'outcome', 'discussion_summary', 'next_action', 'follow_up_date'
        ]
        widgets = {
            'contact_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'contact_method': forms.Select(attrs={'class': 'form-control'}),
            'contacted_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of person contacted'
            }),
            'outcome': forms.Select(attrs={'class': 'form-control'}),
            'discussion_summary': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Summary of discussion'
            }),
            'next_action': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Next action to take (optional)'
            }),
            'follow_up_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['next_action'].required = False
        self.fields['follow_up_date'].required = False
    
    def save(self, commit=True):
        """Save contact record."""
        contact = super().save(commit=False)
        
        if self.repossession:
            contact.repossession = self.repossession
        
        if self.user:
            contact.created_by = self.user
        
        if commit:
            contact.save()
        
        return contact


class RepossessionRecoveryAttemptForm(forms.ModelForm):
    """Form for recording recovery attempts."""
    
    class Meta:
        model = RepossessionRecoveryAttempt
        fields = [
            'attempt_date', 'location', 'agent_name', 'team_size',
            'result', 'details', 'police_involved', 'police_report_number',
            'vehicle_condition', 'cost_incurred'
        ]
        widgets = {
            'attempt_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'location': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Location of recovery attempt'
            }),
            'agent_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Recovery agent name'
            }),
            'team_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'result': forms.Select(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Details of the recovery attempt'
            }),
            'police_involved': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'police_report_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Police report number'
            }),
            'vehicle_condition': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Vehicle condition (if recovered)'
            }),
            'cost_incurred': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.repossession = kwargs.pop('repossession', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['police_report_number'].required = False
        self.fields['vehicle_condition'].required = False
    
    def save(self, commit=True):
        """Save recovery attempt."""
        attempt = super().save(commit=False)
        
        if self.repossession:
            attempt.repossession = self.repossession
        
        if self.user:
            attempt.created_by = self.user
        
        if commit:
            attempt.save()
            
            # If successful, update repossession status
            if attempt.result == 'SUCCESSFUL':
                self.repossession.mark_as_recovered(
                    recovery_date=attempt.attempt_date.date(),
                    location=attempt.location
                )
        
        return attempt


class RepossessionSearchForm(forms.Form):
    """Form for searching repossessions."""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by number, vehicle, or client...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(Repossession.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    reason = forms.ChoiceField(
        required=False,
        choices=[('', 'All reasons')] + list(Repossession.REASON_CHOICES),
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
    
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Any agent'
        })
    )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date must be before end date.')
        
        return cleaned_data


class RepossessionCompletionForm(forms.Form):
    """Form for completing a repossession."""
    
    resolution_type = forms.ChoiceField(
        choices=[
            ('PAID_IN_FULL', 'Paid in Full'),
            ('AUCTIONED', 'Vehicle Auctioned'),
            ('RETURNED', 'Returned to Client'),
            ('WRITTEN_OFF', 'Written Off'),
            ('OTHER', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Resolution details'
        })
    )
    
    completion_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        initial=date.today
    )