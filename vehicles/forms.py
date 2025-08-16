from django import forms
from .models import Vehicle, VehicleImage, VehicleExpense

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        exclude = ['added_by', 'created_at', 'updated_at']

class VehicleImageForm(forms.ModelForm):
    class Meta:
        model = VehicleImage
        fields = ['image', 'caption', 'is_primary']

class VehicleExpenseForm(forms.ModelForm):
    class Meta:
        model = VehicleExpense
        exclude = ['vehicle', 'created_at', 'recorded_by']
