"""
Forms for the insurance app
Handles insurance providers, policies, claims, and payments
"""
from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import InsuranceProvider, InsurancePolicy, InsuranceClaim, InsurancePayment
from apps.vehicles.models import Vehicle
from apps.clients.models import Client


# ==================== INSURANCE PROVIDER FORM ====================

class InsuranceProviderForm(forms.ModelForm):
    """
    Form for creating and updating insurance providers
    """
    
    # Phone validator
    phone_regex = forms.RegexField(
        regex=r'^(\+?254|0)[17]\d{8}$',
        error_messages={'invalid': "Phone number must be in format: '0712345678' or '+254712345678'"}
    )
    
    class Meta:
        model = InsuranceProvider
        fields = [
            'name', 'registration_number',
            'phone_primary', 'phone_secondary', 'email', 'website',
            'physical_address', 'postal_address', 'city',
            'contact_person_name', 'contact_person_phone', 'contact_person_email',
            'notes', 'is_active'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Insurance Provider Name'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Registration Number (Optional)'
            }),
            'phone_primary': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0712345678'
            }),
            'phone_secondary': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0723456789 (Optional)'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'email@provider.com'
            }),
            'website': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'https://www.provider.com'
            }),
            'physical_address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Physical Office Address',
                'rows': 3
            }),
            'postal_address': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'P.O. Box (Optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'City'
            }),
            'contact_person_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Contact Person Name (Optional)'
            }),
            'contact_person_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0712345678 (Optional)'
            }),
            'contact_person_email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'contact@provider.com (Optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 3
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
            }),
        }
    
    def clean_name(self):
        """Validate provider name uniqueness"""
        name = self.cleaned_data.get('name')
        provider_id = self.instance.pk
        
        if InsuranceProvider.objects.filter(name__iexact=name).exclude(pk=provider_id).exists():
            raise ValidationError("An insurance provider with this name already exists.")
        
        return name


# ==================== INSURANCE POLICY FORM ====================

class InsurancePolicyForm(forms.ModelForm):
    """
    Form for creating and updating insurance policies
    """
    
    class Meta:
        model = InsurancePolicy
        fields = [
            'vehicle', 'provider', 'client',
            'policy_number', 'policy_type',
            'start_date', 'end_date',
            'premium_amount', 'sum_insured', 'excess_amount',
            'certificate', 'status',
            'coverage_details', 'notes'
        ]
        
        widgets = {
            'vehicle': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'provider': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'client': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'policy_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Policy Number'
            }),
            'policy_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'premium_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'sum_insured': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'excess_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'certificate': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'coverage_details': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Coverage details and terms (Optional)',
                'rows': 3
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active providers
        self.fields['provider'].queryset = InsuranceProvider.objects.filter(is_active=True)
        
        # Set default dates
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now().date()
            self.fields['end_date'].initial = timezone.now().date() + timedelta(days=365)
    
    def clean_policy_number(self):
        """Validate policy number uniqueness"""
        policy_number = self.cleaned_data.get('policy_number')
        policy_id = self.instance.pk
        
        if InsurancePolicy.objects.filter(policy_number=policy_number).exclude(pk=policy_id).exists():
            raise ValidationError("A policy with this number already exists.")
        
        return policy_number
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        sum_insured = cleaned_data.get('sum_insured')
        excess_amount = cleaned_data.get('excess_amount')
        
        # Validate date range
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")
            
            # Check if policy duration is reasonable (max 2 years)
            duration = (end_date - start_date).days
            if duration > 730:  # 2 years
                raise ValidationError("Policy duration cannot exceed 2 years.")
        
        # Validate excess amount
        if excess_amount and sum_insured:
            if excess_amount > (sum_insured * Decimal('0.5')):
                raise ValidationError("Excess amount cannot exceed 50% of sum insured.")
        
        return cleaned_data


# ==================== BULK OPERATIONS FORMS ====================

class BulkPolicyReminderForm(forms.Form):
    """
    Form for sending bulk reminders for expiring policies
    """
    REMINDER_TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('both', 'SMS & Email'),
    ]
    
    days_threshold = forms.IntegerField(
        min_value=1,
        max_value=90,
        initial=30,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '30'
        }),
        help_text='Send reminders for policies expiring within this many days'
    )
    
    reminder_type = forms.ChoiceField(
        choices=REMINDER_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    custom_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Custom message (Optional). Use {policy_number}, {expiry_date}, {vehicle} as placeholders',
            'rows': 4
        })
    )
    
    def clean_days_threshold(self):
        """Validate days threshold"""
        days = self.cleaned_data.get('days_threshold')
        
        if days < 1:
            raise ValidationError("Days threshold must be at least 1.")
        
        if days > 90:
            raise ValidationError("Days threshold cannot exceed 90 days.")
        
        return days


class PolicyCancellationForm(forms.Form):
    """
    Form for cancelling insurance policies
    """
    CANCELLATION_REASON_CHOICES = [
        ('sold', 'Vehicle Sold'),
        ('switched_provider', 'Switched to Another Provider'),
        ('total_loss', 'Vehicle Total Loss'),
        ('client_request', 'Client Request'),
        ('non_payment', 'Non-Payment of Premium'),
        ('other', 'Other'),
    ]
    
    cancellation_reason = forms.ChoiceField(
        choices=CANCELLATION_REASON_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    cancellation_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )
    
    refund_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        help_text='Pro-rata refund amount (if applicable)'
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Cancellation notes',
            'rows': 3
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default cancellation date to today
        self.fields['cancellation_date'].initial = timezone.now().date()
    
    def clean_cancellation_date(self):
        """Validate cancellation date"""
        cancellation_date = self.cleaned_data.get('cancellation_date')
        
        if cancellation_date > timezone.now().date():
            raise ValidationError("Cancellation date cannot be in the future.")
        
        return cancellation_date


class InsuranceQuoteForm(forms.Form):
    """
    Form for generating insurance quotes
    """
    vehicle_make = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Vehicle Make'
        })
    )
    
    vehicle_model = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Vehicle Model'
        })
    )
    
    vehicle_year = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '2020'
        })
    )
    
    vehicle_value = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    
    policy_type = forms.ChoiceField(
        choices=InsurancePolicy.POLICY_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    coverage_duration = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=12,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '12'
        }),
        help_text='Coverage duration in months'
    )
    
    driver_age = forms.IntegerField(
        min_value=18,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '25'
        }),
        help_text='Driver age (affects premium)'
    )
    
    has_claims_history = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        }),
        label='Has claims history in past 3 years?'
    )
    
    def clean_vehicle_year(self):
        """Validate vehicle year"""
        year = self.cleaned_data.get('vehicle_year')
        current_year = timezone.now().year
        
        if year < 1950:
            raise ValidationError("Vehicle year cannot be before 1950.")
        
        if year > current_year + 1:
            raise ValidationError(f"Vehicle year cannot be after {current_year + 1}.")
        
        return year
    
    def calculate_quote(self):
        """Calculate insurance quote based on form data"""
        if not self.is_valid():
            return None
        
        vehicle_value = self.cleaned_data['vehicle_value']
        policy_type = self.cleaned_data['policy_type']
        coverage_duration = self.cleaned_data['coverage_duration']
        vehicle_year = self.cleaned_data['vehicle_year']
        driver_age = self.cleaned_data.get('driver_age', 25)
        has_claims = self.cleaned_data.get('has_claims_history', False)
        
        # Base premium calculation (simplified)
        if policy_type == 'comprehensive':
            base_rate = Decimal('0.05')  # 5% of vehicle value
        elif policy_type == 'third_party_fire_theft':
            base_rate = Decimal('0.03')  # 3% of vehicle value
        else:  # third_party
            base_rate = Decimal('0.02')  # 2% of vehicle value
        
        base_premium = vehicle_value * base_rate
        
        # Adjust for coverage duration
        duration_factor = Decimal(coverage_duration) / Decimal('12')
        premium = base_premium * duration_factor
        
        # Age adjustment
        current_year = timezone.now().year
        vehicle_age = current_year - vehicle_year
        if vehicle_age > 10:
            premium *= Decimal('1.2')  # 20% increase for old vehicles
        
        # Driver age adjustment
        if driver_age and driver_age < 25:
            premium *= Decimal('1.3')  # 30% increase for young drivers
        elif driver_age and driver_age > 65:
            premium *= Decimal('1.15')  # 15% increase for senior drivers
        
        # Claims history adjustment
        if has_claims:
            premium *= Decimal('1.25')  # 25% increase for claims history
        
        return {
            'base_premium': base_premium,
            'final_premium': premium,
            'vehicle_value': vehicle_value,
            'policy_type': policy_type,
            'coverage_months': coverage_duration,
            'adjustments': {
                'vehicle_age': vehicle_age > 10,
                'young_driver': driver_age and driver_age < 25,
                'senior_driver': driver_age and driver_age > 65,
                'claims_history': has_claims
            }
        }


class ClaimDocumentUploadForm(forms.Form):
    """
    Form for uploading additional claim documents
    """
    DOCUMENT_TYPE_CHOICES = [
        ('photos', 'Accident/Damage Photos'),
        ('police_report', 'Police Report'),
        ('estimate', 'Repair Estimate'),
        ('invoice', 'Repair Invoice'),
        ('medical', 'Medical Reports'),
        ('witness', 'Witness Statement'),
        ('other', 'Other'),
    ]
    
    document_type = forms.ChoiceField(
        choices=DOCUMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    document_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Document description (Optional)',
            'rows': 2
        })
    )
    
    def clean_document_file(self):
        """Validate document file"""
        file = self.cleaned_data.get('document_file')
        
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB.")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            ext = file.name.lower()[file.name.rfind('.'):]
            if ext not in allowed_extensions:
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return file


class PolicyComparisonForm(forms.Form):
    """
    Form for comparing multiple insurance policies
    """
    policies = forms.ModelMultipleChoiceField(
        queryset=InsurancePolicy.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Select 2-5 policies to compare'
    )
    
    def clean_policies(self):
        """Validate number of policies selected"""
        policies = self.cleaned_data.get('policies')
        
        if len(policies) < 2:
            raise ValidationError("Please select at least 2 policies to compare.")
        
        if len(policies) > 5:
            raise ValidationError("You can compare a maximum of 5 policies at once.")
        
        return policies


class ExpiryReminderSettingsForm(forms.Form):
    """
    Form for configuring expiry reminder settings
    """
    enable_reminders = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    
    reminder_days = forms.MultipleChoiceField(
        choices=[
            ('90', '90 days before'),
            ('60', '60 days before'),
            ('30', '30 days before'),
            ('14', '14 days before'),
            ('7', '7 days before'),
            ('3', '3 days before'),
            ('1', '1 day before'),
        ],
        initial=['30', '14', '7'],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Select when to send reminders'
    )
    
    reminder_method = forms.MultipleChoiceField(
        choices=[
            ('sms', 'SMS'),
            ('email', 'Email'),
        ],
        initial=['sms', 'email'],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    
    def clean(self):
        """Validate reminder settings"""
        cleaned_data = super().clean()
        enable_reminders = cleaned_data.get('enable_reminders')
        reminder_days = cleaned_data.get('reminder_days')
        reminder_method = cleaned_data.get('reminder_method')
        
        if enable_reminders:
            if not reminder_days:
                raise ValidationError("Please select at least one reminder timing.")
            
            if not reminder_method:
                raise ValidationError("Please select at least one reminder method.")
        
        return cleaned_data

    
    def clean_certificate(self):
        """Validate certificate file"""
        certificate = self.cleaned_data.get('certificate')
        
        if certificate:
            # Check file size (max 5MB)
            if certificate.size > 5 * 1024 * 1024:
                raise ValidationError("Certificate file size cannot exceed 5MB.")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            ext = certificate.name.lower()[certificate.name.rfind('.'):]
            if ext not in allowed_extensions:
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return certificate


# ==================== INSURANCE CLAIM FORM ====================

class InsuranceClaimForm(forms.ModelForm):
    """
    Form for filing insurance claims
    """
    
    class Meta:
        model = InsuranceClaim
        fields = [
            'policy', 'claim_type', 'incident_date',
            'incident_location', 'incident_description',
            'police_report_number', 'claimed_amount',
            'supporting_documents', 'notes'
        ]
        
        widgets = {
            'policy': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'claim_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'incident_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'incident_location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Location of incident'
            }),
            'incident_description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Detailed description of the incident',
                'rows': 5
            }),
            'police_report_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'OB Number (if applicable)'
            }),
            'claimed_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'supporting_documents': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter only active policies
        self.fields['policy'].queryset = InsurancePolicy.objects.filter(status='active')
    
    def clean_incident_date(self):
        """Validate incident date"""
        incident_date = self.cleaned_data.get('incident_date')
        
        if incident_date > timezone.now().date():
            raise ValidationError("Incident date cannot be in the future.")
        
        # Check if incident is too old (more than 1 year)
        one_year_ago = timezone.now().date() - timedelta(days=365)
        if incident_date < one_year_ago:
            raise ValidationError("Incident date cannot be more than 1 year in the past.")
        
        return incident_date
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        policy = cleaned_data.get('policy')
        incident_date = cleaned_data.get('incident_date')
        claimed_amount = cleaned_data.get('claimed_amount')
        
        # Validate incident occurred during policy coverage
        if policy and incident_date:
            if not (policy.start_date <= incident_date <= policy.end_date):
                raise ValidationError(
                    "Incident date must be within the policy coverage period "
                    f"({policy.start_date} to {policy.end_date})."
                )
        
        # Validate claimed amount doesn't exceed sum insured
        if policy and claimed_amount:
            if claimed_amount > policy.sum_insured:
                raise ValidationError(
                    f"Claimed amount (KES {claimed_amount:,.2f}) cannot exceed "
                    f"sum insured (KES {policy.sum_insured:,.2f})."
                )
        
        return cleaned_data


# ==================== CLAIM UPDATE FORM ====================

class ClaimUpdateForm(forms.ModelForm):
    """
    Form for updating claim status and details (by admin/staff)
    """
    
    class Meta:
        model = InsuranceClaim
        fields = [
            'status', 'approved_amount', 'settled_amount',
            'excess_paid', 'settlement_date',
            'assessor_name', 'assessor_phone', 'assessment_date',
            'assessment_report', 'rejection_reason', 'notes'
        ]
        
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'approved_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'settled_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'excess_paid': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'settlement_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'assessor_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Assessor Name'
            }),
            'assessor_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0712345678'
            }),
            'assessment_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'assessment_report': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'accept': '.pdf,.doc,.docx'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Reason for rejection (if applicable)',
                'rows': 3
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional updates and notes',
                'rows': 3
            }),
        }
    
    def clean(self):
        """Validation for claim updates"""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        approved_amount = cleaned_data.get('approved_amount')
        settled_amount = cleaned_data.get('settled_amount')
        rejection_reason = cleaned_data.get('rejection_reason')
        settlement_date = cleaned_data.get('settlement_date')
        
        # If status is rejected, require rejection reason
        if status == 'rejected' and not rejection_reason:
            self.add_error('rejection_reason', 'Rejection reason is required when rejecting a claim.')
        
        # If status is settled, require settlement date and amount
        if status == 'settled':
            if not settlement_date:
                self.add_error('settlement_date', 'Settlement date is required when marking as settled.')
            if not settled_amount or settled_amount <= 0:
                self.add_error('settled_amount', 'Settlement amount is required when marking as settled.')
        
        # Validate settled amount doesn't exceed approved amount
        if settled_amount and approved_amount:
            if settled_amount > approved_amount:
                raise ValidationError("Settled amount cannot exceed approved amount.")
        
        return cleaned_data


# ==================== INSURANCE PAYMENT FORM ====================

class InsurancePaymentForm(forms.ModelForm):
    """
    Form for recording insurance premium payments
    """
    
    class Meta:
        model = InsurancePayment
        fields = [
            'policy', 'amount', 'payment_date', 'payment_method',
            'transaction_reference', 'notes'
        ]
        
        widgets = {
            'policy': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'transaction_reference': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Transaction Reference'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default payment date to today
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()
    
    def clean_payment_date(self):
        """Validate payment date"""
        payment_date = self.cleaned_data.get('payment_date')
        
        if payment_date > timezone.now().date():
            raise ValidationError("Payment date cannot be in the future.")
        
        return payment_date


# ==================== SEARCH AND FILTER FORMS ====================

class InsurancePolicySearchForm(forms.Form):
    """
    Form for searching and filtering insurance policies
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by policy number, vehicle, or client...'
        })
    )
    
    policy_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + InsurancePolicy.POLICY_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + InsurancePolicy.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    provider = forms.ModelChoiceField(
        required=False,
        queryset=InsuranceProvider.objects.filter(is_active=True),
        empty_label='All Providers',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    expiring_soon = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        })
    )


class InsuranceClaimSearchForm(forms.Form):
    """
    Form for searching and filtering insurance claims
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by claim number, vehicle, or client...'
        })
    )
    
    claim_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + InsuranceClaim.CLAIM_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + InsuranceClaim.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date',
            'placeholder': 'From Date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date',
            'placeholder': 'To Date'
        })
    )


# ==================== POLICY RENEWAL FORM ====================

class PolicyRenewalForm(forms.Form):
    """
    Form for renewing insurance policies
    """
    new_start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )
    
    new_end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )