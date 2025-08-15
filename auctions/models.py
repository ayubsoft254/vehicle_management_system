from django.db import models
from core.models import User
import uuid

class Auction(models.Model):
    """Auction events and management"""
    
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    
    # Dates and Times
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_deadline = models.DateTimeField()
    
    # Financial
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.title} - {self.start_date.date()}"
    
    @property
    def total_vehicles(self):
        return self.auction_vehicles.count()
    
    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.status == 'active'

class AuctionVehicle(models.Model):
    """Vehicles in auction with specific fees and costs"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('sold', 'Sold'),
        ('unsold', 'Unsold'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='auction_vehicles')
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='auction_records')
    
    # Auction Details
    lot_number = models.CharField(max_length=20)
    reserve_price = models.DecimalField(max_digits=12, decimal_places=2)
    starting_bid = models.DecimalField(max_digits=12, decimal_places=2)
    final_bid = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Fees and Costs (as specified in requirements)
    valuation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advertisement_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Buyer Information (if sold)
    buyer_name = models.CharField(max_length=100, blank=True)
    buyer_phone = models.CharField(max_length=20, blank=True)
    buyer_id = models.CharField(max_length=20, blank=True)
    
    # Status and Notes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    # Metadata
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('auction', 'lot_number')
        ordering = ['lot_number']
    
    def __str__(self):
        return f"Lot {self.lot_number}: {self.vehicle}"
    
    @property
    def total_vehicle_cost(self):
        """Calculate total cost for vehicle costing module"""
        return (
            self.vehicle.purchase_price + 
            self.valuation_fee + 
            self.advertisement_fee + 
            self.parking_fee + 
            self.other_expenses
        )
    
    @property
    def is_sold(self):
        return self.status == 'sold' and self.final_bid is not None