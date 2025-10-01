"""
Forms for the client app
Handles client registration, vehicle assignment, document uploads, and payments
"""
from django import forms
from django.core.validators import RegexValidator, MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Client, ClientVehicle, ClientDocument, Payment, InstallmentPlan
from apps.vehicles.models import Vehicle


class ClientForm(forms.ModelForm):
    """
    Form for creating and updating client information
    """
    # Phone number validator
    phone_regex = RegexValidator(
        regex=r'^(\+?254|0)[17]\d{8}$',
        message="Phone number must be in format: '0712345678' or '+254712345678'"
    )
    
    phone_primary = forms.CharField(
        validators=[phone_regex],
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0712345678'
        })
    )
    
    phone_secondary = forms.CharField(
        validators=[phone_regex],
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0723456789 (Optional)'
        })
    )
    
    class Meta:
        model = Client
        fields = [
            'first_name', 'middle_name', 'last_name',
            'id_type', 'id_number',
            'phone_primary', 'phone_secondary', 'email',
            'physical_address', 'postal_address',
            'city', 'county',
            'date_of_birth', 'gender',
            'occupation', 'employer_name', 'employer_phone',
            'monthly_income', 'credit_limit',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship',
            'notes'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'First Name'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Middle Name (Optional)'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Last Name'
            }),
            'id_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'ID/Passport Number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'email@example.com (Optional)'
            }),
            'physical_address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Physical Address',
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
            'county': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'County (Optional)'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Occupation (Optional)'
            }),
            'employer_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Employer Name (Optional)'
            }),
            'employer_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Employer Phone (Optional)'
            }),
            'monthly_income': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'credit_limit': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'emergency_contact_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Emergency Contact Name'
            }),
            'emergency_contact_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Emergency Contact Phone'
            }),
            'emergency_contact_relationship': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Relationship (e.g., Spouse, Parent)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 4
            }),
        }
    
    def clean_id_number(self):
        """Validate ID number uniqueness"""
        id_number = self.cleaned_data.get('id_number')
        client_id = self.instance.pk
        
        # Check if ID number exists for another client
        if Client.objects.filter(id_number=id_number).exclude(pk=client_id).exists():
            raise ValidationError("A client with this ID number already exists.")
        
        return id_number
    
    def clean_email(self):
        """Validate email if provided"""
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
        return email
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        credit_limit = cleaned_data.get('credit_limit')
        monthly_income = cleaned_data.get('monthly_income')
        
        # Ensure credit limit is reasonable based on income
        if credit_limit and monthly_income:
            if credit_limit > (monthly_income * 12):
                raise ValidationError(
                    "Credit limit cannot exceed 12 times the monthly income."
                )
        
        return cleaned_data


class ClientVehicleForm(forms.ModelForm):
    """
    Form for assigning a vehicle to a client and setting up payment plan
    """
    
    class Meta:
        model = ClientVehicle
        fields = [
            'client', 'vehicle',
            'purchase_date', 'purchase_price',
            'deposit_paid', 'monthly_installment', 'installment_months',
            'interest_rate', 'contract_number',
            'notes'
        ]
        
        widgets = {
            'client': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'vehicle': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'deposit_paid': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'monthly_installment': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'installment_months': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '12',
                'min': '1'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'contract_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Contract Number (Optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter only available vehicles
        self.fields['vehicle'].queryset = Vehicle.objects.filter(status='available')
    
    def clean(self):
        """Validate vehicle assignment"""
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        vehicle = cleaned_data.get('vehicle')
        deposit_paid = cleaned_data.get('deposit_paid')
        purchase_price = cleaned_data.get('purchase_price')
        
        # Check if vehicle is already assigned
        if vehicle and vehicle.status != 'available':
            raise ValidationError(f"Vehicle {vehicle} is not available for assignment.")
        
        # Validate deposit
        if deposit_paid and purchase_price:
            if deposit_paid > purchase_price:
                raise ValidationError("Deposit cannot exceed purchase price.")
            if deposit_paid < 0:
                raise ValidationError("Deposit cannot be negative.")
        
        # Check client credit limit
        if client and purchase_price:
            balance = purchase_price - (deposit_paid or 0)
            if balance > client.available_credit:
                raise ValidationError(
                    f"Purchase exceeds client's available credit. "
                    f"Available: KES {client.available_credit:,.2f}"
                )
        
        return cleaned_data


class PaymentForm(forms.ModelForm):
    """
    Form for recording client payments
    """
    
    class Meta:
        model = Payment
        fields = [
            'client_vehicle', 'amount', 'payment_date',
            'payment_method', 'transaction_reference',
            'notes'
        ]
        
        widgets = {
            'client_vehicle': forms.Select(attrs={
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
                'placeholder': 'Transaction/Reference Number'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Payment notes (Optional)',
                'rows': 3
            }),
        }
    
    def clean_amount(self):
        """Validate payment amount"""
        amount = self.cleaned_data.get('amount')
        
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        
        return amount
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        client_vehicle = cleaned_data.get('client_vehicle')
        amount = cleaned_data.get('amount')
        
        # Check if payment exceeds remaining balance
        if client_vehicle and amount:
            if amount > client_vehicle.balance:
                raise ValidationError(
                    f"Payment amount (KES {amount:,.2f}) exceeds remaining balance "
                    f"(KES {client_vehicle.balance:,.2f})"
                )
        
        return cleaned_data


class ClientDocumentForm(forms.ModelForm):
    """
    Form for uploading client documents
    """
    
    class Meta:
        model = ClientDocument
        fields = ['client', 'document_type', 'title', 'file', 'description']
        
        widgets = {
            'client': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'document_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Document Title'
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Document description (Optional)',
                'rows': 3
            }),
        }
    
    def clean_file(self):
        """Validate file upload"""
        file = self.cleaned_data.get('file')
        
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


class ClientSearchForm(forms.Form):
    """
    Form for searching and filtering clients
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by name, ID, or phone...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + Client.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    id_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All ID Types')] + Client.ID_TYPE_CHOICES,
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


class InstallmentPlanForm(forms.ModelForm):
    """
    Form for creating/updating installment plans
    """
    
    class Meta:
        model = InstallmentPlan
        fields = [
            'client_vehicle', 'total_amount', 'deposit',
            'monthly_installment', 'number_of_installments',
            'interest_rate', 'start_date',
            'notes'
        ]
        
        widgets = {
            'client_vehicle': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'total_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'deposit': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'monthly_installment': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'number_of_installments': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '12',
                'min': '1'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Plan notes (Optional)',
                'rows': 3
            }),
        }
    
    def clean(self):
        """Validate installment plan calculations"""
        cleaned_data = super().clean()
        total_amount = cleaned_data.get('total_amount')
        deposit = cleaned_data.get('deposit')
        monthly_installment = cleaned_data.get('monthly_installment')
        number_of_installments = cleaned_data.get('number_of_installments')
        
        if all([total_amount, deposit, monthly_installment, number_of_installments]):
            balance = total_amount - deposit
            total_installments = monthly_installment * number_of_installments
            
            # Allow some tolerance for rounding
            if abs(balance - total_installments) > 1:
                raise ValidationError(
                    f"Payment plan mismatch: Balance (KES {balance:,.2f}) does not match "
                    f"total installments (KES {total_installments:,.2f})"
                )
        
        return cleaned_data