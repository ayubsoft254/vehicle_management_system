"""
Auctions App - Models
Handles vehicle auction management, bidding, and auction results
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import uuid

from apps.vehicles.models import Vehicle
from apps.clients.models import Client

User = get_user_model()


# ============================================================================
# CUSTOM MANAGERS
# ============================================================================

class AuctionManager(models.Manager):
    """Custom manager for Auction model"""
    
    def active(self):
        """Get all active auctions"""
        now = timezone.now()
        return self.filter(
            status='active',
            start_date__lte=now,
            end_date__gte=now
        )
    
    def upcoming(self):
        """Get all upcoming auctions"""
        return self.filter(
            status='scheduled',
            start_date__gt=timezone.now()
        )
    
    def completed(self):
        """Get all completed auctions"""
        return self.filter(status='completed')
    
    def expired(self):
        """Get expired but not closed auctions"""
        return self.filter(
            status='active',
            end_date__lt=timezone.now()
        )


class BidManager(models.Manager):
    """Custom manager for Bid model"""
    
    def winning_bids(self):
        """Get all winning bids"""
        return self.filter(is_winning_bid=True)
    
    def for_auction(self, auction):
        """Get all bids for a specific auction"""
        return self.filter(auction=auction).order_by('-bid_amount', 'created_at')
    
    def by_bidder(self, user):
        """Get all bids by a specific user"""
        return self.filter(bidder=user).order_by('-created_at')


# ============================================================================
# AUCTION MODEL
# ============================================================================

class Auction(models.Model):
    """
    Main auction model representing a vehicle auction event
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    AUCTION_TYPE_CHOICES = [
        ('standard', 'Standard Auction'),
        ('reserve', 'Reserve Auction'),
        ('no_reserve', 'No Reserve Auction'),
        ('silent', 'Silent Auction'),
        ('live', 'Live Auction'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction_number = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Auction Type & Status
    auction_type = models.CharField(max_length=20, choices=AUCTION_TYPE_CHOICES, default='standard')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    
    # Vehicle Information
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='auctions'
    )
    
    # Pricing
    starting_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reserve_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Minimum price seller will accept (hidden from bidders)"
    )
    current_bid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    bid_increment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Minimum amount each bid must increase"
    )
    buy_now_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Optional instant purchase price"
    )
    
    # Dates & Times
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    extended_end_date = models.DateTimeField(null=True, blank=True)
    
    # Bidding Configuration
    allow_proxy_bidding = models.BooleanField(default=True)
    auto_extend = models.BooleanField(
        default=True,
        help_text="Automatically extend auction if bid placed in last 5 minutes"
    )
    extension_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Minutes to extend if late bid received"
    )
    minimum_bidders = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    
    # Participation Requirements
    require_registration = models.BooleanField(default=True)
    registration_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    require_deposit = models.BooleanField(default=False)
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Results
    winner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_auctions'
    )
    winning_bid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    reserve_met = models.BooleanField(default=False)
    total_bids = models.IntegerField(default=0)
    unique_bidders = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_auctions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    terms_and_conditions = models.TextField(blank=True)
    inspection_available = models.BooleanField(default=True)
    inspection_location = models.CharField(max_length=255, blank=True)
    featured = models.BooleanField(default=False, help_text="Show in featured auctions")
    
    # SEO & Tracking
    views_count = models.IntegerField(default=0)
    watchers_count = models.IntegerField(default=0)
    
    objects = AuctionManager()
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['auction_number']),
            models.Index(fields=['vehicle']),
        ]
        verbose_name = 'Auction'
        verbose_name_plural = 'Auctions'
    
    def __str__(self):
        return f"{self.auction_number} - {self.title}"
    
    def clean(self):
        """Validate auction data"""
        errors = {}
        
        # Validate dates
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                errors['end_date'] = 'End date must be after start date'
        
        # Validate reserve price
        if self.reserve_price and self.reserve_price < self.starting_price:
            errors['reserve_price'] = 'Reserve price cannot be less than starting price'
        
        # Validate buy now price
        if self.buy_now_price:
            if self.reserve_price and self.buy_now_price < self.reserve_price:
                errors['buy_now_price'] = 'Buy now price cannot be less than reserve price'
            elif self.buy_now_price < self.starting_price:
                errors['buy_now_price'] = 'Buy now price cannot be less than starting price'
        
        # Validate deposit
        if self.require_deposit and not self.deposit_amount:
            errors['deposit_amount'] = 'Deposit amount required when deposit is mandatory'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Generate auction number if not exists
        if not self.auction_number:
            self.auction_number = self.generate_auction_number()
        
        # Auto-update status based on dates
        now = timezone.now()
        if self.status == 'scheduled' and self.start_date <= now < self.end_date:
            self.status = 'active'
        elif self.status == 'active' and self.end_date <= now:
            self.status = 'completed'
            if not self.completed_at:
                self.completed_at = now
        
        super().save(*args, **kwargs)
    
    def generate_auction_number(self):
        """Generate unique auction number"""
        prefix = 'AUC'
        date_part = timezone.now().strftime('%Y%m%d')
        
        # Get count of auctions created today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = Auction.objects.filter(created_at__gte=today_start).count() + 1
        
        return f"{prefix}-{date_part}-{count:04d}"
    
    @property
    def is_active(self):
        """Check if auction is currently active"""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )
    
    @property
    def time_remaining(self):
        """Get time remaining in auction"""
        if not self.is_active:
            return None
        return self.end_date - timezone.now()
    
    @property
    def has_ended(self):
        """Check if auction has ended"""
        return timezone.now() > self.end_date
    
    @property
    def reserve_status(self):
        """Get reserve price status"""
        if not self.reserve_price:
            return 'no_reserve'
        if self.current_bid >= self.reserve_price:
            return 'reserve_met'
        return 'reserve_not_met'
    
    def can_place_bid(self, user, amount):
        """Check if user can place bid with given amount"""
        if not self.is_active:
            return False, "Auction is not active"
        
        if self.require_registration:
            if not AuctionParticipant.objects.filter(auction=self, user=user, is_approved=True).exists():
                return False, "You must register for this auction"
        
        min_bid = self.current_bid + self.bid_increment if self.current_bid > 0 else self.starting_price
        if amount < min_bid:
            return False, f"Minimum bid is {min_bid}"
        
        # Check if user is current highest bidder
        latest_bid = self.bids.filter(is_active=True).order_by('-bid_amount').first()
        if latest_bid and latest_bid.bidder == user:
            return False, "You are already the highest bidder"
        
        return True, "Valid bid"
    
    def extend_auction(self):
        """Extend auction end time"""
        if self.auto_extend:
            self.extended_end_date = self.end_date + timezone.timedelta(minutes=self.extension_minutes)
            self.end_date = self.extended_end_date
            self.save(update_fields=['end_date', 'extended_end_date', 'updated_at'])
    
    def finalize_auction(self):
        """Finalize auction and determine winner"""
        if self.status != 'active':
            return
        
        winning_bid = self.bids.filter(is_active=True).order_by('-bid_amount').first()
        
        if winning_bid:
            self.winner = winning_bid.bidder
            self.winning_bid_amount = winning_bid.bid_amount
            self.reserve_met = self.reserve_price is None or winning_bid.bid_amount >= self.reserve_price
            
            # Mark winning bid
            winning_bid.is_winning_bid = True
            winning_bid.save(update_fields=['is_winning_bid'])
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


# ============================================================================
# AUCTION PARTICIPANT MODEL
# ============================================================================

class AuctionParticipant(models.Model):
    """
    Registered participants for an auction
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='auction_participations'
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auction_participations'
    )
    
    # Registration Details
    registered_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_participants'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Financial
    registration_fee_paid = models.BooleanField(default=False)
    deposit_paid = models.BooleanField(default=False)
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    deposit_refunded = models.BooleanField(default=False)
    
    # Bidding Activity
    total_bids = models.IntegerField(default=0)
    highest_bid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Proxy Bidding
    proxy_bid_enabled = models.BooleanField(default=False)
    proxy_max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Notifications
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['auction', 'user']
        ordering = ['-registered_at']
        indexes = [
            models.Index(fields=['auction', 'user']),
            models.Index(fields=['is_approved']),
        ]
        verbose_name = 'Auction Participant'
        verbose_name_plural = 'Auction Participants'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.auction.auction_number}"
    
    def approve(self, approved_by):
        """Approve participant registration"""
        self.is_approved = True
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save()


# ============================================================================
# BID MODEL
# ============================================================================

class Bid(models.Model):
    """
    Individual bid placed on an auction
    """
    
    BID_TYPE_CHOICES = [
        ('manual', 'Manual Bid'),
        ('proxy', 'Proxy Bid'),
        ('auto', 'Automatic Bid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name='bids'
    )
    bidder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bids'
    )
    
    # Bid Details
    bid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    bid_type = models.CharField(max_length=10, choices=BID_TYPE_CHOICES, default='manual')
    
    # Status
    is_active = models.BooleanField(default=True)
    is_winning_bid = models.BooleanField(default=False)
    is_outbid = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Technical Details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    objects = BidManager()
    
    class Meta:
        ordering = ['-bid_amount', 'created_at']
        indexes = [
            models.Index(fields=['auction', '-bid_amount', 'created_at']),
            models.Index(fields=['bidder', '-created_at']),
            models.Index(fields=['is_winning_bid']),
        ]
        verbose_name = 'Bid'
        verbose_name_plural = 'Bids'
    
    def __str__(self):
        return f"{self.bidder.get_full_name()} - ${self.bid_amount} on {self.auction.auction_number}"
    
    def clean(self):
        """Validate bid"""
        can_bid, message = self.auction.can_place_bid(self.bidder, self.bid_amount)
        if not can_bid:
            raise ValidationError(message)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update auction current bid
            self.auction.current_bid = self.bid_amount
            self.auction.total_bids += 1
            
            # Update unique bidders count
            unique_bidders = self.auction.bids.values('bidder').distinct().count()
            self.auction.unique_bidders = unique_bidders
            
            self.auction.save(update_fields=['current_bid', 'total_bids', 'unique_bidders', 'updated_at'])
            
            # Mark previous bids as outbid
            Bid.objects.filter(
                auction=self.auction,
                is_active=True
            ).exclude(id=self.id).update(is_outbid=True)
            
            # Update participant stats
            participant = AuctionParticipant.objects.filter(
                auction=self.auction,
                user=self.bidder
            ).first()
            
            if participant:
                participant.total_bids += 1
                if not participant.highest_bid or self.bid_amount > participant.highest_bid:
                    participant.highest_bid = self.bid_amount
                participant.save(update_fields=['total_bids', 'highest_bid'])


# ============================================================================
# AUCTION WATCHLIST MODEL
# ============================================================================

class AuctionWatchlist(models.Model):
    """
    Users watching/following auctions
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name='watchers'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='watched_auctions'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    notify_before_end = models.BooleanField(default=True)
    notify_on_outbid = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['auction', 'user']
        ordering = ['-added_at']
        verbose_name = 'Auction Watchlist'
        verbose_name_plural = 'Auction Watchlists'
    
    def __str__(self):
        return f"{self.user.get_full_name()} watching {self.auction.auction_number}"


# ============================================================================
# AUCTION RESULT MODEL
# ============================================================================

class AuctionResult(models.Model):
    """
    Final results and post-auction details
    """
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Payment Pending'),
        ('partial', 'Partial Payment'),
        ('paid', 'Fully Paid'),
        ('failed', 'Payment Failed'),
        ('refunded', 'Refunded'),
    ]
    
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.OneToOneField(
        Auction,
        on_delete=models.CASCADE,
        related_name='result'
    )
    
    # Winner Information
    winner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auction_wins'
    )
    winning_bid = models.ForeignKey(
        Bid,
        on_delete=models.SET_NULL,
        null=True,
        related_name='win_results'
    )
    final_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment Information
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_due_date = models.DateTimeField()
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery Information
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    delivery_scheduled_date = models.DateTimeField(null=True, blank=True)
    delivery_completed_date = models.DateTimeField(null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    
    # Additional Costs
    buyers_premium = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Additional fee charged to buyer"
    )
    taxes = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Auction Result'
        verbose_name_plural = 'Auction Results'
    
    def __str__(self):
        return f"Result for {self.auction.auction_number}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.final_price + self.buyers_premium + self.taxes + self.shipping_cost
        super().save(*args, **kwargs)
    
    @property
    def payment_progress(self):
        """Get payment progress percentage"""
        if self.total_amount == 0:
            return 0
        return (self.amount_paid / self.total_amount) * 100
    
    @property
    def is_payment_overdue(self):
        """Check if payment is overdue"""
        return (
            self.payment_status == 'pending' and
            timezone.now() > self.payment_due_date
        )