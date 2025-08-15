import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import User


class Vehicle(models.Model):
    """Vehicle inventory model with detailed specifications"""
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
        ('repossessed', 'Repossessed'),
        ('auctioned', 'Auctioned'),
        ('maintenance', 'Under Maintenance'),
        ('damaged', 'Damaged'),
    ]
    
    TRANSMISSION_CHOICES = [
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
        ('cvt', 'CVT'),
        ('semi_auto', 'Semi-Automatic'),
    ]
    
    FUEL_TYPE_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
        ('lpg', 'LPG'),
    ]
    
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('very_good', 'Very Good'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='vehicles')
    
    # Basic Information
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField(validators=[MinValueValidator(1900), MaxValueValidator(2030)])
    vin = models.CharField(max_length=17, unique=True, help_text="Vehicle Identification Number")
    license_plate = models.CharField(max_length=20, blank=True)
    
    # Specifications
    engine_size = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)
    mileage = models.PositiveIntegerField(help_text="Mileage in kilometers")
    color = models.CharField(max_length=30)
    doors = models.PositiveIntegerField(default=4)
    seats = models.PositiveIntegerField(default=5)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    
    # Pricing
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    minimum_deposit = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    location = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Metadata
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_vehicles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.vin})"
    
    @property
    def full_name(self):
        return f"{self.year} {self.make} {self.model}"
    
    @property
    def is_available(self):
        return self.status == 'available'

class VehicleImage(models.Model):
    """Multiple images for each vehicle"""
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='vehicles/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'uploaded_at']
    
    def __str__(self):
        return f"{self.vehicle} - Image {self.id}"

class VehicleExpense(models.Model):
    """Track vehicle-specific expenses for costing analysis"""
    
    EXPENSE_CATEGORIES = [
        ('purchase', 'Purchase Cost'),
        ('transport', 'Transportation'),
        ('repair', 'Repairs & Maintenance'),
        ('insurance', 'Insurance'),
        ('registration', 'Registration & Licensing'),
        ('cleaning', 'Cleaning & Detailing'),
        ('storage', 'Storage & Parking'),
        ('inspection', 'Inspection'),
        ('other', 'Other'),
    ]
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    receipt_number = models.CharField(max_length=50, blank=True)
    vendor = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.vehicle} - {self.category}: {self.amount}"