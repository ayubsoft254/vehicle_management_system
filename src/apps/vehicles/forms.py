"""
Vehicles Forms
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Vehicle, VehiclePhoto, VehicleHistory
from utils.constants import VehicleStatus
from decimal import Decimal


class VehicleForm(forms.ModelForm):
    """Form for creating/editing vehicles"""
    
    class Meta:
        model = Vehicle
        fields = [
            'make', 'model', 'year', 'vin', 'registration_number',
            'color', 'mileage', 'fuel_type', 'transmission',
            'engine_size', 'body_type', 'seats', 'doors',
            'condition', 'purchase_price', 'selling_price', 'deposit_required',
            'status', 'is_active', 'is_featured',
            'description', 'features', 'location', 'purchase_date'
        ]
        widgets = {
            'make': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g., Toyota, Honda, Nissan',
                'required': 'required'
            }),
            'model': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g., Corolla, Civic, Patrol',
                'required': 'required'
            }),
            'year': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '2020',
                'required': 'required'
            }),
            'vin': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '17-character VIN',
                'maxlength': '17',
                'required': 'required'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'KAA 123A'
            }),
            'color': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'White, Black, Silver, etc.',
                'required': 'required'
            }),
            'mileage': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Kilometers',
                'required': 'required'
            }),
            'fuel_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'transmission': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'engine_size': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '1.5L or 2000cc'
            }),
            'body_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'seats': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'doors': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Purchase price in KES',
                'step': '0.01',
                'required': 'required'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Selling price in KES',
                'step': '0.01',
                'required': 'required'
            }),
            'deposit_required': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Minimum deposit in KES',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 4,
                'placeholder': 'Detailed description of the vehicle...'
            }),
            'features': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'AC, Power Steering, Sunroof, etc.'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Current location of vehicle'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date',
                'required': 'required'
            }),
        }
        labels = {
            'vin': 'VIN (Vehicle Identification Number)',
            'mileage': 'Mileage (KM)',
            'is_active': 'Active in Inventory',
            'is_featured': 'Featured Vehicle',
        }
    
    def clean_vin(self):
        """Validate VIN is unique (case-insensitive)"""
        vin = self.cleaned_data.get('vin', '').upper()
        
        # Check for duplicate VIN (excluding current instance)
        existing = Vehicle.objects.filter(vin=vin)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise ValidationError('A vehicle with this VIN already exists.')
        
        return vin
    
    def clean_registration_number(self):
        """Validate registration number is unique"""
        reg_number = self.cleaned_data.get('registration_number', '').upper()
        
        if reg_number:
            # Check for duplicate (excluding current instance)
            existing = Vehicle.objects.filter(registration_number=reg_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A vehicle with this registration number already exists.')
        
        return reg_number
    
    def clean(self):
        cleaned_data = super().clean()
        selling_price = cleaned_data.get('selling_price')
        purchase_price = cleaned_data.get('purchase_price')
        deposit_required = cleaned_data.get('deposit_required')
        
        # Validate selling price is not less than purchase price (warning, not error)
        if selling_price and purchase_price and selling_price < purchase_price:
            self.add_error('selling_price', 
                'Warning: Selling price is less than purchase price. This will result in a loss.')
        
        # Validate deposit is not more than selling price
        if deposit_required and selling_price and deposit_required > selling_price:
            raise ValidationError('Deposit cannot be more than selling price.')
        
        return cleaned_data


class VehiclePhotoForm(forms.ModelForm):
    """Form for uploading vehicle photos"""
    
    class Meta:
        model = VehiclePhoto
        fields = ['image', 'caption', 'is_primary', 'order']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Optional photo description'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'order': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default value for order field
        self.fields['order'].required = False
        self.fields['order'].initial = 0
        # Make caption optional
        self.fields['caption'].required = False
        # Make is_primary optional with default False
        self.fields['is_primary'].required = False
        self.fields['is_primary'].initial = False
        # Ensure image is required
        self.fields['image'].required = True
    
    def clean_order(self):
        """Ensure order field always has a valid value"""
        order = self.cleaned_data.get('order')
        if order is None or order == '':
            return 0
        return order
    
    def clean_is_primary(self):
        """Ensure is_primary field always has a valid boolean value"""
        is_primary = self.cleaned_data.get('is_primary')
        if is_primary is None:
            return False
        return is_primary


class VehicleSearchForm(forms.Form):
    """Form for searching and filtering vehicles"""
    
    search = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Search by make, model, VIN, or registration...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        label='Status',
        choices=[('', 'All Status')] + VehicleStatus.CHOICES,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    make = forms.CharField(
        required=False,
        label='Make',
        widget=forms.TextInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Any make'
        })
    )
    
    year_from = forms.IntegerField(
        required=False,
        label='Year From',
        widget=forms.NumberInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'From'
        })
    )
    
    year_to = forms.IntegerField(
        required=False,
        label='Year To',
        widget=forms.NumberInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'To'
        })
    )
    
    price_from = forms.DecimalField(
        required=False,
        label='Price From',
        widget=forms.NumberInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Min price',
            'step': '1000'
        })
    )
    
    price_to = forms.DecimalField(
        required=False,
        label='Price To',
        widget=forms.NumberInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Max price',
            'step': '1000'
        })
    )
    
    fuel_type = forms.ChoiceField(
        required=False,
        label='Fuel Type',
        choices=[('', 'All')] + [
            ('petrol', 'Petrol'),
            ('diesel', 'Diesel'),
            ('electric', 'Electric'),
            ('hybrid', 'Hybrid'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    transmission = forms.ChoiceField(
        required=False,
        label='Transmission',
        choices=[('', 'All')] + [
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ('cvt', 'CVT'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    body_type = forms.ChoiceField(
        required=False,
        label='Body Type',
        choices=[('', 'All')] + [
            ('sedan', 'Sedan'),
            ('suv', 'SUV'),
            ('hatchback', 'Hatchback'),
            ('pickup', 'Pickup Truck'),
            ('van', 'Van'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )


class VehicleStatusChangeForm(forms.Form):
    """Form for changing vehicle status"""
    
    new_status = forms.ChoiceField(
        label='New Status',
        choices=VehicleStatus.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'rows': 3,
            'placeholder': 'Optional notes about this status change...'
        })
    )


class BulkVehicleActionForm(forms.Form):
    """Form for bulk actions on vehicles"""
    
    action = forms.ChoiceField(
        label='Action',
        choices=[
            ('', 'Select Action'),
            ('activate', 'Activate'),
            ('deactivate', 'Deactivate'),
            ('feature', 'Mark as Featured'),
            ('unfeature', 'Remove Featured'),
            ('change_status', 'Change Status'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    new_status = forms.ChoiceField(
        label='New Status (if changing status)',
        choices=[('', 'Select Status')] + VehicleStatus.CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    vehicle_ids = forms.CharField(
        widget=forms.HiddenInput()
    )