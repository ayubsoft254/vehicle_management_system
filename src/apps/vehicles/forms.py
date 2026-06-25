"""
Vehicles Forms
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Vehicle, VehiclePhoto, VehicleHistory, TrackerAgent, ClearingAgent, Broker, JapanSupplier
from utils.constants import VehicleStatus, VehicleLocation
from decimal import Decimal
from django.forms import HiddenInput


class VehicleForm(forms.ModelForm):
    """Form for creating/editing vehicles"""
    
    class Meta:
        model = Vehicle
        fields = [
            'make', 'model', 'year', 'vin', 'engine_number', 'registration_number',
            'color', 'mileage', 'fuel_type', 'transmission',
            'engine_size', 'body_type', 'seats', 'doors',
            'condition', 'purchase_price', 'purchase_price_usd', 'purchase_usd_rate',
            'selling_price', 'website_price', 'deposit_required',
            'duty_cost', 'clearance_cost',
            'status', 'is_active', 'is_featured',
            'description', 'features', 'location', 'location_moved_date',
            'location_driver_name', 'location_driver_phone', 'location_driver_id_number',
            'ship_name', 'vessel_number',
            'purchase_date'
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
            'engine_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Engine number'
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
            'purchase_price_usd': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g. 8500',
                'step': '0.01',
                'id': 'id_purchase_price_usd',
            }),
            'purchase_usd_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g. 130.00',
                'step': '0.0001',
                'id': 'id_purchase_usd_rate',
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Vehicle cost in KES',
                'step': '0.01',
                'required': 'required'
            }),
            'website_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Website price in KES (optional)',
                'step': '0.01'
            }),
            'deposit_required': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Minimum deposit in KES',
                'step': '0.01'
            }),
            'duty_cost': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Import duty cost in KES',
                'step': '0.01'
            }),
            'clearance_cost': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Clearance/port cost in KES',
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
            'location': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            }),
            'location_moved_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }),
            'location_driver_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Driver full name'
            }),
            'location_driver_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Driver phone number'
            }),
            'location_driver_id_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Driver ID number'
            }),
            'ship_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Name of the vessel/ship'
            }),
            'vessel_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Vessel identification number'
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
    
    def __init__(self, *args, **kwargs):
        """Initialize form and set required attribute for fields with defaults"""
        self.can_view_prices = kwargs.pop('can_view_prices', True)
        super().__init__(*args, **kwargs)

        # Fields with defaults in the model - make optional in form
        optional_fields = [
            'seats', 'condition', 'deposit_required', 'duty_cost',
            'clearance_cost', 'location',
            'location_moved_date', 'location_driver_name',
            'location_driver_phone', 'location_driver_id_number',
            'website_price', 'purchase_price_usd', 'purchase_usd_rate',
        ]
        for field_name in optional_fields:
            self.fields[field_name].required = False
            # Remove HTML5 required attribute from widget if present
            if 'required' in self.fields[field_name].widget.attrs:
                del self.fields[field_name].widget.attrs['required']

        self.fields['location'].choices = [('', 'Select vehicle location')] + list(VehicleLocation.CHOICES)

        # Selling price is derived from total cost on the form and server side.
        self.fields['selling_price'].widget.attrs['readonly'] = 'readonly'

        # Non-admin users can input costs but must not see vehicle prices.
        if not self.can_view_prices:
            for field_name in ['purchase_price', 'selling_price', 'website_price', 'deposit_required']:
                self.fields[field_name].required = False
                self.fields[field_name].widget = HiddenInput()

            if not self.is_bound:
                if self.instance and self.instance.pk:
                    self.initial['purchase_price'] = self.instance.purchase_price or Decimal('0.00')
                    self.initial['selling_price'] = self.instance.selling_price or Decimal('0.00')
                    self.initial['website_price'] = self.instance.website_price or self.instance.selling_price or Decimal('0.00')
                    self.initial['deposit_required'] = self.instance.deposit_required or Decimal('0.00')
                else:
                    self.initial['purchase_price'] = Decimal('0.00')
                    self.initial['selling_price'] = Decimal('0.00')
                    self.initial['website_price'] = Decimal('0.00')
                    self.initial['deposit_required'] = Decimal('0.00')
        
        # Set initial values for fields with model defaults (for new instances)
        if not self.instance.pk:
            self.fields['seats'].initial = 5
            self.fields['condition'].initial = 'good'
            self.fields['deposit_required'].initial = 0.0
    
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
        reg_number = self.cleaned_data.get('registration_number')
        
        # Handle blank/None values - registration is optional
        if not reg_number:
            return reg_number
        
        # Convert to uppercase for comparison
        reg_number = reg_number.upper()
        
        # Check for duplicate (excluding current instance)
        existing = Vehicle.objects.filter(registration_number=reg_number)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise ValidationError('A vehicle with this registration number already exists.')
        
        return reg_number

    def clean_deposit_required(self):
        """Treat blank deposit as 0.00 so deposit stays optional."""
        deposit_required = self.cleaned_data.get('deposit_required')
        return deposit_required if deposit_required is not None else Decimal('0.00')
    
    def clean(self):
        cleaned_data = super().clean()
        purchase_price = cleaned_data.get('purchase_price')
        deposit_required = cleaned_data.get('deposit_required') or Decimal('0.00')
        duty_cost = cleaned_data.get('duty_cost') or Decimal('0.00')
        clearance_cost = cleaned_data.get('clearance_cost') or Decimal('0.00')
        website_price = cleaned_data.get('website_price')
        location = cleaned_data.get('location')
        location_moved_date = cleaned_data.get('location_moved_date')
        location_driver_name = (cleaned_data.get('location_driver_name') or '').strip()
        location_driver_phone = (cleaned_data.get('location_driver_phone') or '').strip()
        location_driver_id_number = (cleaned_data.get('location_driver_id_number') or '').strip()

        if not self.can_view_prices:
            if self.instance and self.instance.pk:
                purchase_price = self.instance.purchase_price or Decimal('0.00')
                cleaned_data['purchase_price'] = purchase_price
                cleaned_data['website_price'] = self.instance.website_price
                cleaned_data['deposit_required'] = self.instance.deposit_required or Decimal('0.00')
            else:
                purchase_price = Decimal('0.00')
                cleaned_data['purchase_price'] = purchase_price
                cleaned_data['website_price'] = Decimal('0.00')
                cleaned_data['deposit_required'] = Decimal('0.00')

        if purchase_price is not None:
            cleaned_data['selling_price'] = purchase_price + duty_cost + clearance_cost

        selling_price = cleaned_data.get('selling_price')
        if website_price is None:
            cleaned_data['website_price'] = selling_price
        else:
            if website_price < 0:
                raise ValidationError('Website price cannot be negative.')
            cleaned_data['website_price'] = website_price

        if location and not location_moved_date:
            self.add_error('location_moved_date', 'Please provide the date the vehicle was moved to this location.')

        cleaned_data['location_driver_name'] = location_driver_name
        cleaned_data['location_driver_phone'] = location_driver_phone
        cleaned_data['location_driver_id_number'] = location_driver_id_number
        
        # Validate deposit is not more than selling price
        if deposit_required and selling_price and deposit_required > selling_price:
            raise ValidationError('Deposit cannot be more than selling price.')

        return cleaned_data


class VehicleMoveForm(forms.Form):
    """Dedicated form for moving a vehicle between tracked locations."""

    location = forms.ChoiceField(
        choices=[('', 'Select vehicle location')] + list(VehicleLocation.CHOICES),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
        })
    )
    location_moved_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'type': 'date'
        })
    )
    location_driver_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Driver full name'
        })
    )
    location_driver_phone = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Driver phone number'
        })
    )
    location_driver_id_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Driver ID number'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'rows': 3,
            'placeholder': 'Optional move notes, for example transfer to showroom or yard rearrangement'
        })
    )

    def __init__(self, *args, **kwargs):
        vehicle = kwargs.pop('vehicle', None)
        super().__init__(*args, **kwargs)

        if vehicle:
            self.fields['location'].initial = vehicle.location
            self.fields['location_moved_date'].initial = vehicle.location_moved_date
            self.fields['location_driver_name'].initial = vehicle.location_driver_name
            self.fields['location_driver_phone'].initial = vehicle.location_driver_phone
            self.fields['location_driver_id_number'].initial = vehicle.location_driver_id_number

    def clean_notes(self):
        return (self.cleaned_data.get('notes') or '').strip()


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
    
    location = forms.ChoiceField(
        required=False,
        label='Location',
        choices=[('', 'All Locations')] + VehicleLocation.CHOICES,
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

    ALLOWED_STATUS_CHOICES = [
        choice for choice in VehicleStatus.CHOICES
        if choice[0] != VehicleStatus.REPOSSESSED
    ]
    
    new_status = forms.ChoiceField(
        label='New Status',
        choices=ALLOWED_STATUS_CHOICES,
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
        choices=[('', 'Select Status')] + [
            choice for choice in VehicleStatus.CHOICES if choice[0] != VehicleStatus.REPOSSESSED
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    vehicle_ids = forms.CharField(
        widget=forms.HiddenInput()
    )

# ==================== TRACKER AGENT FORM ====================

_FC = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'


class TrackerAgentForm(forms.ModelForm):
    class Meta:
        model = TrackerAgent
        fields = ['name', 'phone', 'email', 'notes']
        widgets = {
            'name':  forms.TextInput(attrs={'class': _FC, 'placeholder': 'Agent name'}),
            'phone': forms.TextInput(attrs={'class': _FC, 'placeholder': '+254...'}),
            'email': forms.EmailInput(attrs={'class': _FC, 'placeholder': 'agent@example.com'}),
            'notes': forms.Textarea(attrs={'class': _FC, 'rows': 3, 'placeholder': 'Optional notes'}),
        }


# ==================== CLEARING AGENT FORM ====================

class ClearingAgentForm(forms.ModelForm):
    class Meta:
        model = ClearingAgent
        fields = ['name', 'phone', 'email', 'notes']
        widgets = {
            'name':  forms.TextInput(attrs={'class': _FC, 'placeholder': 'Agent name'}),
            'phone': forms.TextInput(attrs={'class': _FC, 'placeholder': '+254...'}),
            'email': forms.EmailInput(attrs={'class': _FC, 'placeholder': 'agent@example.com'}),
            'notes': forms.Textarea(attrs={'class': _FC, 'rows': 3, 'placeholder': 'Optional notes'}),
        }


# ==================== JAPAN SUPPLIER FORM ====================

class JapanSupplierForm(forms.ModelForm):
    class Meta:
        model = JapanSupplier
        fields = ['name', 'phone', 'email', 'country', 'notes']
        widgets = {
            'name':    forms.TextInput(attrs={'class': _FC, 'placeholder': 'Supplier name'}),
            'phone':   forms.TextInput(attrs={'class': _FC, 'placeholder': '+81...'}),
            'email':   forms.EmailInput(attrs={'class': _FC, 'placeholder': 'supplier@example.jp'}),
            'country': forms.TextInput(attrs={'class': _FC, 'placeholder': 'Japan'}),
            'notes':   forms.Textarea(attrs={'class': _FC, 'rows': 3, 'placeholder': 'Optional notes'}),
        }


# ==================== BROKER FORM ====================

class BrokerForm(forms.ModelForm):
    class Meta:
        model = Broker
        fields = ['name', 'id_number', 'phone', 'email', 'notes']
        widgets = {
            'name':      forms.TextInput(attrs={'class': _FC, 'placeholder': 'Broker full name'}),
            'id_number': forms.TextInput(attrs={'class': _FC, 'placeholder': 'National ID or passport'}),
            'phone':     forms.TextInput(attrs={'class': _FC, 'placeholder': '+254...'}),
            'email':     forms.EmailInput(attrs={'class': _FC, 'placeholder': 'broker@example.com'}),
            'notes':     forms.Textarea(attrs={'class': _FC, 'rows': 3, 'placeholder': 'Optional notes'}),
        }
