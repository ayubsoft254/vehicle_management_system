"""
Vehicles Models
Manage vehicle inventory with complete specifications and history
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from utils.constants import VehicleStatus
from utils.validators import validate_vin, validate_registration_number
import os


class VehicleManager(models.Manager):
    """Custom manager for Vehicle model"""
    
    def available(self):
        """Get all available vehicles"""
        return self.filter(status=VehicleStatus.AVAILABLE, is_active=True)
    
    def sold(self):
        """Get all sold vehicles"""
        return self.filter(status=VehicleStatus.SOLD)
    
    def reserved(self):
        """Get all reserved vehicles"""
        return self.filter(status=VehicleStatus.RESERVED)
    
    def repossessed(self):
        """Get all repossessed vehicles"""
        return self.filter(status=VehicleStatus.REPOSSESSED)
    
    def auctioned(self):
        """Get all auctioned vehicles"""
        return self.filter(status=VehicleStatus.AUCTIONED)
    
    def in_maintenance(self):
        """Get all vehicles in maintenance"""
        return self.filter(status=VehicleStatus.MAINTENANCE)


class Vehicle(models.Model):
    """
    Main vehicle model
    Stores complete vehicle information and specifications
    """
    
    # Basic Information
    make = models.CharField(
        'Make',
        max_length=100,
        help_text='Vehicle manufacturer (e.g., Toyota, Honda, Nissan)'
    )
    
    model = models.CharField(
        'Model',
        max_length=100,
        help_text='Vehicle model (e.g., Corolla, Civic, Patrol)'
    )
    
    year = models.IntegerField(
        'Year of Manufacture',
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(timezone.now().year + 1)
        ],
        help_text='Year the vehicle was manufactured'
    )
    
    # Identification
    vin = models.CharField(
        'VIN (Vehicle Identification Number)',
        max_length=17,
        unique=True,
        validators=[validate_vin],
        help_text='17-character unique vehicle identifier'
    )
    
    registration_number = models.CharField(
        'Registration Number',
        max_length=20,
        unique=True,
        validators=[validate_registration_number],
        blank=True,
        null=True,
        help_text='Vehicle registration/license plate number (e.g., KAA 123A)'
    )
    
    # Specifications
    color = models.CharField(
        'Color',
        max_length=50,
        help_text='Exterior color'
    )
    
    mileage = models.IntegerField(
        'Mileage (KM)',
        validators=[MinValueValidator(0)],
        help_text='Current mileage in kilometers'
    )
    
    fuel_type = models.CharField(
        'Fuel Type',
        max_length=20,
        choices=[
            ('petrol', 'Petrol'),
            ('diesel', 'Diesel'),
            ('electric', 'Electric'),
            ('hybrid', 'Hybrid'),
            ('other', 'Other'),
        ],
        default='petrol'
    )
    
    transmission = models.CharField(
        'Transmission',
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ('cvt', 'CVT'),
        ],
        default='manual'
    )
    
    engine_size = models.CharField(
        'Engine Size',
        max_length=20,
        blank=True,
        help_text='Engine capacity (e.g., 1.5L, 2000cc)'
    )
    
    body_type = models.CharField(
        'Body Type',
        max_length=50,
        choices=[
            ('sedan', 'Sedan'),
            ('suv', 'SUV'),
            ('hatchback', 'Hatchback'),
            ('pickup', 'Pickup Truck'),
            ('van', 'Van'),
            ('coupe', 'Coupe'),
            ('wagon', 'Station Wagon'),
            ('other', 'Other'),
        ],
        blank=True
    )
    
    seats = models.IntegerField(
        'Number of Seats',
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        default=5
    )
    
    doors = models.IntegerField(
        'Number of Doors',
        validators=[MinValueValidator(2), MaxValueValidator(6)],
        default=4
    )
    
    # Condition
    condition = models.CharField(
        'Condition',
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        default='good'
    )
    
    # Pricing
    purchase_price = models.DecimalField(
        'Purchase Price',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Price at which vehicle was purchased'
    )
    
    selling_price = models.DecimalField(
        'Selling Price',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Current selling price'
    )
    
    deposit_required = models.DecimalField(
        'Deposit Required',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Minimum deposit required for purchase'
    )
    
    # Status
    status = models.CharField(
        'Status',
        max_length=20,
        choices=VehicleStatus.CHOICES,
        default=VehicleStatus.AVAILABLE,
        db_index=True
    )
    
    is_active = models.BooleanField(
        'Active',
        default=True,
        help_text='Whether vehicle is active in inventory'
    )
    
    is_featured = models.BooleanField(
        'Featured',
        default=False,
        help_text='Display as featured vehicle'
    )
    
    # Additional Information
    description = models.TextField(
        'Description',
        blank=True,
        help_text='Additional details about the vehicle'
    )
    
    features = models.TextField(
        'Features',
        blank=True,
        help_text='Special features (e.g., AC, Power Steering, Sunroof)'
    )
    
    location = models.CharField(
        'Location',
        max_length=200,
        blank=True,
        help_text='Where vehicle is currently located'
    )
    
    # Dates
    purchase_date = models.DateField(
        'Purchase Date',
        help_text='Date vehicle was purchased/acquired'
    )
    
    date_added = models.DateTimeField(
        'Date Added',
        auto_now_add=True
    )
    
    date_sold = models.DateField(
        'Date Sold',
        blank=True,
        null=True
    )
    
    last_updated = models.DateTimeField(
        'Last Updated',
        auto_now=True
    )
    
    # Relationships
    added_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='vehicles_added'
    )
    
    # Custom manager
    objects = VehicleManager()
    
    class Meta:
        db_table = 'vehicles'
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        ordering = ['-date_added']
        indexes = [
            models.Index(fields=['status', '-date_added']),
            models.Index(fields=['make', 'model']),
            models.Index(fields=['vin']),
            models.Index(fields=['registration_number']),
            models.Index(fields=['is_active', 'status']),
        ]
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model} - {self.registration_number or self.vin[:8]}"
    
    @property
    def full_name(self):
        """Get full vehicle name"""
        return f"{self.year} {self.make} {self.model}"
    
    @property
    def profit(self):
        """Calculate potential profit"""
        return self.selling_price - self.purchase_price
    
    @property
    def profit_percentage(self):
        """Calculate profit percentage"""
        if self.purchase_price > 0:
            return (self.profit / self.purchase_price) * 100
        return 0
    
    @property
    def is_available(self):
        """Check if vehicle is available for sale"""
        return self.status == VehicleStatus.AVAILABLE and self.is_active
    
    @property
    def main_photo(self):
        """Get main/primary photo"""
        return self.photos.filter(is_primary=True).first() or self.photos.first()
    
    def get_status_color(self):
        """Get color for status badge"""
        color_map = {
            VehicleStatus.AVAILABLE: 'green',
            VehicleStatus.RESERVED: 'yellow',
            VehicleStatus.SOLD: 'blue',
            VehicleStatus.REPOSSESSED: 'red',
            VehicleStatus.AUCTIONED: 'purple',
            VehicleStatus.MAINTENANCE: 'orange',
        }
        return color_map.get(self.status, 'gray')
    
    def change_status(self, new_status, user, notes=''):
        """Change vehicle status and log history"""
        old_status = self.status
        self.status = new_status
        self.save()
        
        # Create history entry
        VehicleHistory.objects.create(
            vehicle=self,
            changed_by=user,
            old_status=old_status,
            new_status=new_status,
            notes=notes
        )
        
        # Update date_sold if status is SOLD
        if new_status == VehicleStatus.SOLD and not self.date_sold:
            self.date_sold = timezone.now().date()
            self.save()


class VehiclePhoto(models.Model):
    """
    Vehicle photos
    Multiple photos can be associated with one vehicle
    """
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    
    image = models.ImageField(
        'Photo',
        upload_to='vehicles/%Y/%m/',
        help_text='Vehicle photo'
    )
    
    caption = models.CharField(
        'Caption',
        max_length=200,
        blank=True,
        help_text='Optional photo description'
    )
    
    is_primary = models.BooleanField(
        'Primary Photo',
        default=False,
        help_text='Main photo to display'
    )
    
    order = models.IntegerField(
        'Display Order',
        default=0,
        help_text='Order to display photos'
    )
    
    uploaded_at = models.DateTimeField(
        'Uploaded At',
        auto_now_add=True
    )
    
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='vehicle_photos_uploaded'
    )
    
    class Meta:
        db_table = 'vehicle_photos'
        verbose_name = 'Vehicle Photo'
        verbose_name_plural = 'Vehicle Photos'
        ordering = ['order', '-uploaded_at']
    
    def __str__(self):
        return f"Photo for {self.vehicle.full_name}"
    
    def save(self, *args, **kwargs):
        """Ensure only one primary photo per vehicle"""
        if self.is_primary:
            # Set all other photos for this vehicle as non-primary
            VehiclePhoto.objects.filter(
                vehicle=self.vehicle,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Delete the image file when photo is deleted"""
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)


class VehicleHistory(models.Model):
    """
    Track vehicle status changes and history
    Complete audit trail for each vehicle
    """
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    changed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='vehicle_changes'
    )
    
    old_status = models.CharField(
        'Previous Status',
        max_length=20,
        choices=VehicleStatus.CHOICES
    )
    
    new_status = models.CharField(
        'New Status',
        max_length=20,
        choices=VehicleStatus.CHOICES
    )
    
    notes = models.TextField(
        'Notes',
        blank=True,
        help_text='Additional notes about the change'
    )
    
    timestamp = models.DateTimeField(
        'Changed At',
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'vehicle_history'
        verbose_name = 'Vehicle History'
        verbose_name_plural = 'Vehicle History'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.vehicle.full_name} - {self.old_status} → {self.new_status}"