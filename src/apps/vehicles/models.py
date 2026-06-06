"""
Vehicles Models
Manage vehicle inventory with complete specifications and history
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from utils.constants import VehicleStatus, VehicleLocation
from utils.validators import validate_vin, validate_license_plate
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
        help_text='Year the vehicle was manufactured'
    )
    
    # Identification
    vin = models.CharField(
        'VIN (Vehicle Identification Number)',
        max_length=100,
        unique=True,        
        help_text='Unique vehicle identifier (can include hyphens)'
    )
    
    registration_number = models.CharField(
        'Registration Number',
        max_length=20,
        unique=True,        
        blank=True,
        null=True,
        help_text='Vehicle registration/license plate number (e.g., KAA 123A)'
    )
    
    engine_number = models.CharField(
        'Engine Number',
        max_length=100,
        blank=True,
        null=True,
        help_text='Vehicle engine number'
    )
    
    # Specifications
    color = models.CharField(
        'Color',
        max_length=50,
        help_text='Exterior color'
    )
    
    mileage = models.IntegerField(
        'Mileage (KM)',        
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
        default=5
    )
    
    doors = models.IntegerField(
        'Number of Doors',       
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
    
    # Additional Costs
    duty_cost = models.DecimalField(
        'Duty Cost',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Import duty cost'
    )
    
    clearance_cost = models.DecimalField(
        'Clearance Cost',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Port/customs clearance cost'
    )
    
    commission_cost = models.DecimalField(
        'Commission Cost',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text='Commission or agent fees'
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
        choices=VehicleLocation.CHOICES,
        help_text='Current location of the vehicle'
    )

    location_moved_date = models.DateField(
        'Location Move Date',
        blank=True,
        null=True,
        help_text='Date the vehicle was moved to its current location'
    )

    location_driver_name = models.CharField(
        'Driver Name',
        max_length=200,
        blank=True,
        help_text='Name of the driver who moved the vehicle'
    )

    location_driver_phone = models.CharField(
        'Driver Phone Number',
        max_length=50,
        blank=True,
        help_text='Phone number of the driver who moved the vehicle'
    )

    location_driver_id_number = models.CharField(
        'Driver ID Number',
        max_length=100,
        blank=True,
        help_text='National ID or identification number of the driver'
    )
    
    # Shipping Information
    ship_name = models.CharField(
        'Ship Name',
        max_length=200,
        blank=True,
        null=True,
        help_text='Name of the vessel/ship used for transport'
    )
    
    vessel_number = models.CharField(
        'Vessel Number',
        max_length=100,
        blank=True,
        null=True,
        help_text='Vessel identification number or code'
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
        reg_or_vin = self.registration_number or self.vin[:8]
        return f"{self.year} {self.make} {self.model} - {reg_or_vin}"

    def save(self, *args, **kwargs):
        """Persist vehicle and append a location history row when movement details change."""
        previous_vehicle = None
        should_log_location = False
        move_notes = getattr(self, '_location_move_notes', '') or ''

        if self.pk:
            previous_vehicle = type(self).objects.filter(pk=self.pk).first()
            if previous_vehicle:
                should_log_location = any([
                    previous_vehicle.location != self.location,
                    previous_vehicle.location_moved_date != self.location_moved_date,
                    previous_vehicle.location_driver_name != self.location_driver_name,
                    previous_vehicle.location_driver_phone != self.location_driver_phone,
                    previous_vehicle.location_driver_id_number != self.location_driver_id_number,
                ])
        else:
            should_log_location = bool(
                self.location and
                self.location_moved_date and
                self.location_driver_name and
                self.location_driver_phone and
                self.location_driver_id_number
            )

        super().save(*args, **kwargs)

        if should_log_location and self.location:
            VehicleLocationHistory.objects.create(
                vehicle=self,
                from_location=previous_vehicle.location if previous_vehicle else '',
                to_location=self.location,
                moved_date=self.location_moved_date,
                driver_name=self.location_driver_name,
                driver_phone=self.location_driver_phone,
                driver_id_number=self.location_driver_id_number,
                notes=move_notes,
            )

        if hasattr(self, '_location_move_notes'):
            delattr(self, '_location_move_notes')

    @property
    def location_driver_summary(self):
        """Return a compact driver summary for the current location record."""
        parts = [self.location_driver_name, self.location_driver_phone, self.location_driver_id_number]
        return ' | '.join([part for part in parts if part])
    
    @property
    def full_name(self):
        """Get full vehicle name"""
        return f"{self.year} {self.make} {self.model}"

    @property
    def showroom_date(self):
        """Return the move date only when the vehicle is in the showroom."""
        if self.location == VehicleLocation.SHOWROOM:
            return self.location_moved_date
        return None

    @property
    def total_program_cost(self):
        """Calculate total program cost for this vehicle."""
        extra_cost_total = self.extra_costs.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return (
            (self.purchase_price or Decimal('0.00'))
            + (self.duty_cost or Decimal('0.00'))
            + (self.clearance_cost or Decimal('0.00'))
            + (self.commission_cost or Decimal('0.00'))
            + extra_cost_total
        )
    
    @property
    def profit(self):
        """Calculate potential profit from selling price minus total program cost."""
        return (self.selling_price or Decimal('0.00')) - self.total_program_cost
    
    @property
    def profit_percentage(self):
        """Calculate profit percentage"""
        base_cost = self.total_program_cost
        if base_cost > 0:
            return (self.profit / base_cost) * 100
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


class VehicleExtraCost(models.Model):
    """
    Additional costs for vehicle (e.g., repairs, customization, other fees)
    """
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='extra_costs'
    )
    
    description = models.CharField(
        'Description',
        max_length=255,
        help_text='Description of the cost'
    )
    
    amount = models.DecimalField(
        'Amount',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Cost amount'
    )
    
    date_added = models.DateTimeField(
        'Date Added',
        auto_now_add=True
    )
    
    added_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicle_extra_costs_added'
    )
    
    class Meta:
        db_table = 'vehicle_extra_costs'
        verbose_name = 'Vehicle Extra Cost'
        verbose_name_plural = 'Vehicle Extra Costs'
        ordering = ['-date_added']
    
    def __str__(self):
        return f"{self.vehicle} - {self.description}: {self.amount}"


class VehicleLocationHistory(models.Model):
    """Historical log of vehicle location movements."""

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='location_history'
    )

    from_location = models.CharField(
        'From Location',
        max_length=200,
        blank=True,
        choices=VehicleLocation.CHOICES,
    )

    to_location = models.CharField(
        'To Location',
        max_length=200,
        choices=VehicleLocation.CHOICES,
    )

    moved_date = models.DateField(
        'Moved Date',
        blank=True,
        null=True,
    )

    driver_name = models.CharField(
        'Driver Name',
        max_length=200,
        blank=True,
    )

    driver_phone = models.CharField(
        'Driver Phone Number',
        max_length=50,
        blank=True,
    )

    driver_id_number = models.CharField(
        'Driver ID Number',
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        'Move Notes',
        blank=True,
        help_text='Optional reason or context for the move'
    )

    recorded_at = models.DateTimeField(
        'Recorded At',
        auto_now_add=True,
    )

    class Meta:
        db_table = 'vehicle_location_history'
        verbose_name = 'Vehicle Location History'
        verbose_name_plural = 'Vehicle Location History'
        ordering = ['-moved_date', '-recorded_at']

    def __str__(self):
        return f"{self.vehicle} moved to {self.get_to_location_display()}"

    @property
    def driver_summary(self):
        """Return a compact driver summary for this move record."""
        parts = [self.driver_name, self.driver_phone, self.driver_id_number]
        return ' | '.join([part for part in parts if part])


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
        if self.is_primary and self.vehicle.pk:
            # Set all other photos for this vehicle as non-primary
            # Only if vehicle has been saved (has a pk)
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