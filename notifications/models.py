from django.db import models
from core.models import User
import uuid
from auctions.models import Auction

class NotificationTemplate(models.Model):
    """Templates for different types of notifications"""
    
    NOTIFICATION_TYPES = [
        ('payment_due', 'Payment Due Reminder'),
        ('payment_overdue', 'Payment Overdue'),
        ('insurance_expiry', 'Insurance Expiry Warning'),
        ('auction_notification', 'Auction Notification'),
        ('client_update', 'Client Update'),
        ('vehicle_status', 'Vehicle Status Change'),
        ('welcome', 'Welcome Message'),
        ('payment_received', 'Payment Confirmation'),
    ]
    
    DELIVERY_METHODS = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('both', 'SMS & Email'),
    ]
    
    name = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, unique=True)
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHODS)
    
    # Email Content
    email_subject = models.CharField(max_length=200, blank=True)
    email_body = models.TextField(blank=True)
    
    # SMS Content
    sms_message = models.TextField(max_length=160, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_send = models.BooleanField(default=False)
    
    # Variables help text
    available_variables = models.TextField(
        blank=True,
        help_text="Available variables: {client_name}, {vehicle}, {amount}, {due_date}, etc."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.notification_type})"

class Notification(models.Model):
    """Individual notification records"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    DELIVERY_METHODS = [
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='notifications')
    
    # Delivery Details
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHODS)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # Content
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    
    # Scheduling
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(blank=True, null=True)
    
    # Status and Response
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_status = models.TextField(blank=True)  # Provider response
    error_message = models.TextField(blank=True)
    
    # Related Objects (optional references)
    related_payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, blank=True, null=True)
    related_vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, blank=True, null=True)
    related_auction = models.ForeignKey(Auction, on_delete=models.CASCADE, blank=True, null=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.template.notification_type} to {self.recipient}"