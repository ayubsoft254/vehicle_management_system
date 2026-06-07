"""
Forms for the client app
Handles client registration, vehicle assignment, document uploads, and payments
"""
from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime
import json
from .models import Client, ClientVehicle, ClientDocument
from apps.payments.models import Payment, InstallmentPlan
from apps.vehicles.models import Vehicle
from utils.constants import ClientStatus
from django.db.models import Q


class ClientForm(forms.ModelForm):
    """
    Form for creating and updating client information
    """
    # Phone fields — no format validation, accept any international number
    phone_primary = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'e.g. 0712345678 or +254712345678'
        })
    )
    
    phone_secondary = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Alternative phone (Optional)'
        })
    )
    
    class Meta:
        model = Client
        fields = [
            'first_name', 'other_names', 'last_name',
            'id_type', 'id_number', 'kra_pin',
            'phone_primary', 'phone_secondary', 'email',
            'physical_address', 'postal_address',
            'city', 'county',
            'date_of_birth', 'gender',
            'occupation', 'employer',
            'monthly_income',
            'next_of_kin_name', 'next_of_kin_phone',
            'next_of_kin_relationship', 'next_of_kin_address',
            'notes'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'First Name'
            }),
            'other_names': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Other Names (Optional)'
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
            'kra_pin': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g. A012345678Z (Optional)'
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
            'employer': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Employer (Optional)'
            }),
            'monthly_income': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'next_of_kin_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Next of Kin Name'
            }),
            'next_of_kin_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Next of Kin Phone'
            }),
            'next_of_kin_relationship': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Relationship (e.g., Spouse, Parent)'
            }),
            'next_of_kin_address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Next of Kin Address',
                'rows': 3
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
            'vehicle',
            'broker_name', 'broker_id_no', 'broker_phone_no',
            'purchase_date', 'purchase_price',
            'final_selling_price', 'extra_costs_total', 'extra_costs_json',
            'deposit_paid', 'payment_type',
            'remainder_payment_type', 'monthly_payment_date', 'weekly_payment_day',
            'allow_flexible_payments',
            'monthly_installment', 'installment_months',
            'commission_amount',
            'notes'
        ]
        
        widgets = {
            'vehicle': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent vehicle-select',
                'data-placeholder': 'Search by Make, Model, VIN or Registration...'
            }),
            'broker_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Broker name'
            }),
            'broker_id_no': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Broker ID number'
            }),
            'broker_phone_no': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Broker phone number'
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
            'final_selling_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'extra_costs_total': forms.NumberInput(attrs={
                'class': 'hidden',
                'step': '0.01',
                'min': '0'
            }),
            'extra_costs_json': forms.HiddenInput(),
            'deposit_paid': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'payment_type': forms.RadioSelect(attrs={
                'class': 'flex gap-6'
            }),
            'remainder_payment_type': forms.RadioSelect(attrs={
                'class': 'flex gap-4'
            }),
            'monthly_payment_date': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '12',
                'min': '1',
                'max': '31'
            }),
            'weekly_payment_day': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'allow_flexible_payments': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
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
            'commission_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # Extract client if passed explicitly (for new assignments)
        self.client = kwargs.pop('client', None)
        super().__init__(*args, **kwargs)
        
        # If updating, get client from instance
        if self.instance and self.instance.pk:
            self.client = self.instance.client
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                Q(status='available') | Q(pk=self.instance.vehicle.pk)
            )
            if not self.is_bound:
                if self.instance.client_purchase_price and self.instance.client_purchase_price > 0:
                    self.fields['purchase_price'].initial = self.instance.client_purchase_price
                if self.instance.final_selling_price and self.instance.final_selling_price > 0:
                    self.fields['final_selling_price'].initial = self.instance.final_selling_price
                else:
                    self.fields['final_selling_price'].initial = self.instance.purchase_price
                self.fields['extra_costs_total'].initial = self.instance.extra_costs_total or Decimal('0.00')
                self.fields['extra_costs_json'].initial = self.instance.extra_costs_json or '[]'
        else:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(status='available')
        
        # Customize vehicle field to display chassis number
        self.fields['vehicle'].label_from_instance = lambda obj: f"{obj.year} {obj.make} {obj.model} - {obj.vin}"
        
        # Make optional fields non-required
        optional_fields = [
            'remainder_payment_type', 'monthly_payment_date',
            'weekly_payment_day', 'monthly_installment', 'installment_months', 
            'broker_name', 'broker_id_no', 'broker_phone_no', 'commission_amount'
        ]
        for field_name in optional_fields:
            self.fields[field_name].required = False

        self.fields['extra_costs_total'].required = False
        self.fields['extra_costs_json'].required = False
    
    def clean(self):
        """Validate vehicle assignment and payment plan"""
        cleaned_data = super().clean()
        client = self.client
        vehicle = cleaned_data.get('vehicle')
        deposit_paid = cleaned_data.get('deposit_paid')
        purchase_price = cleaned_data.get('purchase_price')
        final_selling_price = cleaned_data.get('final_selling_price')
        extra_costs_total = cleaned_data.get('extra_costs_total') or Decimal('0.00')
        payment_type = cleaned_data.get('payment_type')
        remainder_payment_type = cleaned_data.get('remainder_payment_type')
        monthly_payment_date = cleaned_data.get('monthly_payment_date')
        weekly_payment_day = cleaned_data.get('weekly_payment_day')
        installment_months = cleaned_data.get('installment_months')

        if purchase_price is None:
            purchase_price = Decimal('0.00')

        if final_selling_price is None:
            final_selling_price = purchase_price

        if extra_costs_total < 0:
            raise ValidationError("Extra costs cannot be negative.")

        effective_purchase_price = (final_selling_price - extra_costs_total).quantize(Decimal('0.01'))
        if effective_purchase_price < 0:
            raise ValidationError("Final selling price cannot be lower than total extra costs.")

        cleaned_data['purchase_price'] = effective_purchase_price
        cleaned_data['final_selling_price'] = final_selling_price.quantize(Decimal('0.01'))
        cleaned_data['extra_costs_total'] = extra_costs_total.quantize(Decimal('0.01'))
        
        # Check if vehicle is already assigned
        if vehicle and vehicle.status != 'available':
            # Allow if updating and vehicle hasn't changed
            if not (self.instance and self.instance.pk and self.instance.vehicle == vehicle):
                raise ValidationError(f"Vehicle {vehicle} is not available for assignment.")
        
        # Validate deposit
        if deposit_paid and effective_purchase_price:
            if deposit_paid > effective_purchase_price:
                raise ValidationError("Deposit cannot exceed net client price.")
            if deposit_paid < 0:
                raise ValidationError("Deposit cannot be negative.")

        if payment_type == 'full' and effective_purchase_price:
            cleaned_data['deposit_paid'] = effective_purchase_price
            cleaned_data['allow_flexible_payments'] = False
            cleaned_data['remainder_payment_type'] = None
            cleaned_data['monthly_payment_date'] = None
            cleaned_data['weekly_payment_day'] = None
            cleaned_data['installment_months'] = None
            cleaned_data['monthly_installment'] = None
            deposit_paid = effective_purchase_price
        
        # Validate payment type-specific requirements
        if payment_type == 'installment':
            if not installment_months or installment_months < 1:
                raise ValidationError("Please specify the number of months for installment payments.")
            if remainder_payment_type not in ['monthly', 'weekly']:
                raise ValidationError("Please select whether payments are monthly or weekly.")
            if remainder_payment_type == 'monthly' and not monthly_payment_date:
                raise ValidationError("Please specify the day of month for monthly payments.")
            if remainder_payment_type == 'weekly' and weekly_payment_day is None:
                raise ValidationError("Please select the day of week for weekly payments.")
        
        elif payment_type == 'flexible':
            raw_schedule = self.data.get('flexible_installments_json', '[]')
            try:
                installments = json.loads(raw_schedule)
            except json.JSONDecodeError:
                raise ValidationError("Flexible installments are invalid. Please re-enter installment dates and amounts.")

            if not isinstance(installments, list) or len(installments) == 0:
                raise ValidationError("Add at least one installment for flexible payment.")

            balance = (effective_purchase_price or Decimal('0.00')) - (deposit_paid or Decimal('0.00'))
            if balance <= 0:
                raise ValidationError("Flexible installments require a remaining balance after deposit.")

            total_installments = Decimal('0.00')
            for idx, item in enumerate(installments, start=1):
                if not isinstance(item, dict):
                    raise ValidationError(f"Installment {idx} is invalid.")

                due_date = str(item.get('due_date', '')).strip()
                amount_raw = str(item.get('amount', '')).strip()

                if not due_date:
                    raise ValidationError(f"Installment {idx} requires a payment date.")
                try:
                    datetime.strptime(due_date, '%Y-%m-%d')
                except ValueError:
                    raise ValidationError(f"Installment {idx} has an invalid payment date.")

                try:
                    amount = Decimal(amount_raw)
                except Exception:
                    raise ValidationError(f"Installment {idx} has an invalid amount.")

                if amount <= 0:
                    raise ValidationError(f"Installment {idx} amount must be greater than zero.")

                total_installments += amount

            if (total_installments - balance).copy_abs() > Decimal('0.01'):
                raise ValidationError(
                    f"Flexible installment total must equal remaining balance (KES {balance:,.2f}). "
                    f"Current total is KES {total_installments:,.2f}."
                )

            # Flexible schedule is custom, so derive normalized values for persistence.
            cleaned_data['allow_flexible_payments'] = True
            cleaned_data['remainder_payment_type'] = None
            cleaned_data['monthly_payment_date'] = None
            cleaned_data['weekly_payment_day'] = None
            cleaned_data['installment_months'] = len(installments)
            cleaned_data['monthly_installment'] = (balance / Decimal(str(len(installments)))).quantize(Decimal('0.01'))
        
        # Check client credit limit (only if a limit is set > 0)
        if client and effective_purchase_price and client.credit_limit > 0:
            balance = effective_purchase_price - (deposit_paid or 0)
            
            # If updating, add back the existing balance to available credit
            if self.instance and self.instance.pk:
                effective_available_credit = client.available_credit + self.instance.balance
            else:
                effective_available_credit = client.available_credit
                
            if balance > effective_available_credit:
                raise ValidationError(
                    f"Purchase exceeds client's available credit. "
                    f"Available: KES {effective_available_credit:,.2f}"
                )
        
        return cleaned_data


class PaymentForm(forms.ModelForm):
    """
    Form for recording client payments
    """
    
    class Meta:
        model = Payment
        fields = [
            'amount', 'payment_date',
            'payment_method', 'transaction_reference',
            'notes'
        ]
        
        widgets = {
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
    
    def __init__(self, *args, **kwargs):
        self.client_vehicle = kwargs.pop('client_vehicle', None)
        super().__init__(*args, **kwargs)
        
    def clean_amount(self):
        """Validate payment amount"""
        amount = self.cleaned_data.get('amount')
        
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        
        return amount
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        
        # Check if payment exceeds remaining balance
        if self.client_vehicle and amount:
            if amount > self.client_vehicle.balance:
                raise ValidationError(
                    f"Payment amount (KES {amount:,.2f}) exceeds remaining balance "
                    f"(KES {self.client_vehicle.balance:,.2f})"
                )
        
        return cleaned_data


class ClientDocumentForm(forms.ModelForm):
    """
    Form for uploading client documents
    """
    
    class Meta:
        model = ClientDocument
        fields = ['document_type', 'title', 'file', 'description']
        
        widgets = {
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
        choices=[('', 'All Status')] + ClientStatus.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    id_type = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All ID Types'),
            ('national_id', 'National ID'),
            ('passport', 'Passport'),
            ('other', 'Other'),
        ],
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
            'monthly_installment', 'number_of_installments',
            'start_date'
        ]
        
        widgets = {
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
            'start_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.client_vehicle = kwargs.pop('client_vehicle', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate installment plan calculations"""
        cleaned_data = super().clean()
        monthly_installment = cleaned_data.get('monthly_installment')
        number_of_installments = cleaned_data.get('number_of_installments')
        
        if self.client_vehicle and monthly_installment and number_of_installments:
            total_amount = self.client_vehicle.purchase_price
            deposit = self.client_vehicle.deposit_paid
            balance = total_amount - deposit
            total_installments = monthly_installment * number_of_installments
            
            # Allow some tolerance for rounding
            if abs(balance - total_installments) > 1:
                raise ValidationError(
                    f"Payment plan mismatch: Balance (KES {balance:,.2f}) does not match "
                    f"total installments (KES {total_installments:,.2f})"
                )
        
        return cleaned_data