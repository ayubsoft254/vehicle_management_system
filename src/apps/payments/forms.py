"""
Forms for the payments app
Handles payment recording, installment plans, and payment schedules
"""
from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from .models import Payment, InstallmentPlan, PaymentSchedule, PaymentReminder
from apps.clients.models import ClientVehicle


# ==================== PAYMENT FORM ====================

class PaymentForm(forms.ModelForm):
    """
    Form for recording payments
    """
    
    class Meta:
        model = Payment
        fields = [
            'amount', 'payment_date', 'payment_method',
            'transaction_reference', 'notes'
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
                'placeholder': 'M-Pesa code, Cheque number, etc.'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes about this payment (Optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.client_vehicle = kwargs.pop('client_vehicle', None)
        super().__init__(*args, **kwargs)
        
        # Set default payment date to today
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()
    
    def clean_amount(self):
        """Validate payment amount"""
        amount = self.cleaned_data.get('amount')
        
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        
        # Check against remaining balance if client_vehicle is provided
        if self.client_vehicle and amount > self.client_vehicle.balance:
            raise ValidationError(
                f"Payment amount (KES {amount:,.2f}) exceeds remaining balance "
                f"(KES {self.client_vehicle.balance:,.2f})"
            )
        
        return amount
    
    def clean_payment_date(self):
        """Validate payment date"""
        payment_date = self.cleaned_data.get('payment_date')
        
        if payment_date > timezone.now().date():
            raise ValidationError("Payment date cannot be in the future.")
        
        # Check if date is too far in the past (more than 1 year)
        one_year_ago = timezone.now().date() - timedelta(days=365)
        if payment_date < one_year_ago:
            raise ValidationError("Payment date cannot be more than 1 year in the past.")
        
        return payment_date
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        transaction_reference = cleaned_data.get('transaction_reference')
        
        # Require transaction reference for certain payment methods
        if payment_method in ['mpesa', 'bank_transfer', 'cheque'] and not transaction_reference:
            self.add_error(
                'transaction_reference',
                f'Transaction reference is required for {payment_method} payments.'
            )
        
        return cleaned_data


# ==================== INSTALLMENT PLAN FORM ====================

class InstallmentPlanForm(forms.ModelForm):
    """
    Form for creating and updating installment plans
    """
    
    class Meta:
        model = InstallmentPlan
        fields = [
            'total_amount', 'deposit', 'monthly_installment',
            'number_of_installments', 'interest_rate',
            'start_date', 'is_active', 'notes'
        ]
        
        widgets = {
            'total_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'deposit': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'monthly_installment': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'number_of_installments': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '12',
                'min': '1'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes about this installment plan (Optional)',
                'rows': 3
            }),
        }
    
    def clean_deposit(self):
        """Validate deposit amount"""
        deposit = self.cleaned_data.get('deposit')
        total_amount = self.cleaned_data.get('total_amount')
        
        if deposit and total_amount and deposit >= total_amount:
            raise ValidationError("Deposit must be less than total amount.")
        
        if deposit < 0:
            raise ValidationError("Deposit cannot be negative.")
        
        return deposit
    
    def clean_number_of_installments(self):
        """Validate number of installments"""
        number = self.cleaned_data.get('number_of_installments')
        
        if number < 1:
            raise ValidationError("Number of installments must be at least 1.")
        
        if number > 120:  # Max 10 years
            raise ValidationError("Number of installments cannot exceed 120 (10 years).")
        
        return number
    
    def clean_interest_rate(self):
        """Validate interest rate"""
        rate = self.cleaned_data.get('interest_rate')
        
        if rate < 0:
            raise ValidationError("Interest rate cannot be negative.")
        
        if rate > 100:
            raise ValidationError("Interest rate cannot exceed 100%.")
        
        return rate
    
    def clean(self):
        """Additional validation for payment calculations"""
        cleaned_data = super().clean()
        total_amount = cleaned_data.get('total_amount')
        deposit = cleaned_data.get('deposit')
        monthly_installment = cleaned_data.get('monthly_installment')
        number_of_installments = cleaned_data.get('number_of_installments')
        interest_rate = cleaned_data.get('interest_rate')
        
        if all([total_amount, deposit, monthly_installment, number_of_installments]):
            # Calculate expected values
            balance_after_deposit = total_amount - deposit
            
            # Calculate with interest if applicable
            if interest_rate and interest_rate > 0:
                interest_amount = balance_after_deposit * (interest_rate / 100) * (number_of_installments / 12)
                total_with_interest = balance_after_deposit + interest_amount
            else:
                total_with_interest = balance_after_deposit
            
            total_installments = monthly_installment * number_of_installments
            
            # Allow for small rounding differences (up to 1 KES)
            difference = abs(total_with_interest - total_installments)
            if difference > 1:
                raise ValidationError(
                    f"Payment plan calculation mismatch: "
                    f"Balance after deposit (KES {total_with_interest:,.2f}) "
                    f"does not match total installments (KES {total_installments:,.2f}). "
                    f"Difference: KES {difference:,.2f}"
                )
        
        return cleaned_data


# ==================== PAYMENT SCHEDULE FORM ====================

class PaymentScheduleForm(forms.ModelForm):
    """
    Form for updating payment schedules
    """
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'due_date', 'amount_due', 'amount_paid',
            'is_paid', 'payment_date', 'notes'
        ]
        
        widgets = {
            'due_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'amount_due': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.00'
            }),
            'is_paid': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional notes (Optional)',
                'rows': 2
            }),
        }
    
    def clean(self):
        """Validate payment schedule data"""
        cleaned_data = super().clean()
        amount_due = cleaned_data.get('amount_due')
        amount_paid = cleaned_data.get('amount_paid')
        is_paid = cleaned_data.get('is_paid')
        payment_date = cleaned_data.get('payment_date')
        
        # Validate amount paid doesn't exceed amount due
        if amount_paid and amount_due and amount_paid > amount_due:
            raise ValidationError(
                f"Amount paid (KES {amount_paid:,.2f}) cannot exceed "
                f"amount due (KES {amount_due:,.2f})"
            )
        
        # If marked as paid, require payment date
        if is_paid and not payment_date:
            self.add_error('payment_date', 'Payment date is required when marked as paid.')
        
        # If payment date is set, ensure it's not in the future
        if payment_date and payment_date > timezone.now().date():
            self.add_error('payment_date', 'Payment date cannot be in the future.')
        
        return cleaned_data


# ==================== PAYMENT REMINDER FORM ====================

class PaymentReminderForm(forms.ModelForm):
    """
    Form for creating payment reminders
    """
    
    class Meta:
        model = PaymentReminder
        fields = [
            'payment_schedule', 'reminder_type', 'message', 'status'
        ]
        
        widgets = {
            'payment_schedule': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'reminder_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'message': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter reminder message...',
                'rows': 4
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to show only unpaid schedules
        self.fields['payment_schedule'].queryset = PaymentSchedule.objects.filter(
            is_paid=False
        ).select_related(
            'installment_plan__client_vehicle__client',
            'installment_plan__client_vehicle__vehicle'
        )
    
    def clean_message(self):
        """Validate reminder message"""
        message = self.cleaned_data.get('message')
        
        if len(message) < 10:
            raise ValidationError("Reminder message must be at least 10 characters long.")
        
        if len(message) > 1000:
            raise ValidationError("Reminder message cannot exceed 1000 characters.")
        
        return message


# ==================== SEARCH AND FILTER FORMS ====================

class PaymentSearchForm(forms.Form):
    """
    Form for searching and filtering payments
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by receipt, client, vehicle, or transaction reference...'
        })
    )
    
    payment_method = forms.ChoiceField(
        required=False,
        choices=[('', 'All Methods')] + Payment.PAYMENT_METHOD_CHOICES,
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
    
    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("'From Date' must be before 'To Date'.")
        
        return cleaned_data


class InstallmentPlanFilterForm(forms.Form):
    """
    Form for filtering installment plans
    """
    STATUS_CHOICES = [
        ('', 'All Plans'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    ]
    
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by client or vehicle...'
        })
    )


class PaymentScheduleFilterForm(forms.Form):
    """
    Form for filtering payment schedules
    """
    STATUS_CHOICES = [
        ('', 'All Schedules'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('due_this_month', 'Due This Month'),
    ]
    
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )


# ==================== BULK PAYMENT FORM ====================

class BulkPaymentForm(forms.Form):
    """
    Form for recording multiple payments at once
    """
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )
    
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Bulk payment notes (Optional)',
            'rows': 2
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default payment date to today
        self.fields['payment_date'].initial = timezone.now().date()


# ==================== PAYMENT CALCULATOR FORM ====================

class PaymentCalculatorForm(forms.Form):
    """
    Form for calculating payment plans
    """
    vehicle_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    
    deposit = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    
    number_of_months = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '12'
        })
    )
    
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    
    def clean(self):
        """Validate calculator inputs"""
        cleaned_data = super().clean()
        vehicle_price = cleaned_data.get('vehicle_price')
        deposit = cleaned_data.get('deposit')
        
        if deposit and vehicle_price and deposit >= vehicle_price:
            raise ValidationError("Deposit must be less than vehicle price.")
        
        return cleaned_data
    
    def calculate_monthly_payment(self):
        """Calculate monthly payment amount"""
        if not self.is_valid():
            return None
        
        vehicle_price = self.cleaned_data['vehicle_price']
        deposit = self.cleaned_data['deposit']
        months = self.cleaned_data['number_of_months']
        interest_rate = self.cleaned_data.get('interest_rate', 0)
        
        balance = vehicle_price - deposit
        
        if interest_rate and interest_rate > 0:
            interest_amount = balance * (interest_rate / 100) * (months / 12)
            total_with_interest = balance + interest_amount
        else:
            interest_amount = 0
            total_with_interest = balance
        
        monthly_payment = total_with_interest / months
        
        return {
            'balance': balance,
            'interest_amount': interest_amount,
            'total_with_interest': total_with_interest,
            'monthly_payment': monthly_payment,
            'total_to_pay': deposit + total_with_interest
        }