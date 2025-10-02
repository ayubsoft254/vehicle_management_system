"""
Auctions App - Forms
Form classes for auction management, bidding, and participant registration
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import timedelta

from .models import Auction, Bid, AuctionParticipant, AuctionResult, AuctionWatchlist
from apps.vehicles.models import Vehicle
from apps.clients.models import Client

User = get_user_model()


# ============================================================================
# AUCTION FORMS
# ============================================================================

class AuctionForm(forms.ModelForm):
    """
    Form for creating and updating auctions
    """
    
    class Meta:
        model = Auction
        fields = [
            'title',
            'description',
            'auction_type',
            'vehicle',
            'starting_price',
            'reserve_price',
            'bid_increment',
            'buy_now_price',
            'start_date',
            'end_date',
            'allow_proxy_bidding',
            'auto_extend',
            'extension_minutes',
            'minimum_bidders',
            'require_registration',
            'registration_fee',
            'require_deposit',
            'deposit_amount',
            'terms_and_conditions',
            'inspection_available',
            'inspection_location',
            'featured',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter auction title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the auction...'
            }),
            'auction_type': forms.Select(attrs={'class': 'form-control'}),
            'vehicle': forms.Select(attrs={'class': 'form-control'}),
            'starting_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'reserve_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional reserve price',
                'step': '0.01'
            }),
            'bid_increment': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '100.00',
                'step': '0.01'
            }),
            'buy_now_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional buy now price',
                'step': '0.01'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'extension_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '60'
            }),
            'minimum_bidders': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'registration_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'deposit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Deposit amount',
                'step': '0.01'
            }),
            'terms_and_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Enter terms and conditions...'
            }),
            'inspection_location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Inspection location address'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter vehicles to only available ones for new auctions
        if not self.instance.pk:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                status__in=['available', 'in_stock']
            )
        
        # Make certain fields required based on conditions
        self.fields['reserve_price'].required = False
        self.fields['buy_now_price'].required = False
        self.fields['deposit_amount'].required = False
    
    def clean_start_date(self):
        """Validate start date"""
        start_date = self.cleaned_data.get('start_date')
        
        if start_date:
            # Start date must be in the future for new auctions
            if not self.instance.pk and start_date < timezone.now():
                raise ValidationError("Start date must be in the future.")
            
            # Don't allow changing start date if auction has already started
            if self.instance.pk and self.instance.status == 'active':
                raise ValidationError("Cannot change start date for active auction.")
        
        return start_date
    
    def clean_end_date(self):
        """Validate end date"""
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')
        
        if end_date and start_date:
            # End date must be after start date
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")
            
            # Minimum auction duration (e.g., 1 hour)
            min_duration = timedelta(hours=1)
            if end_date - start_date < min_duration:
                raise ValidationError("Auction must run for at least 1 hour.")
            
            # Maximum auction duration (e.g., 30 days)
            max_duration = timedelta(days=30)
            if end_date - start_date > max_duration:
                raise ValidationError("Auction cannot run for more than 30 days.")
        
        return end_date
    
    def clean_reserve_price(self):
        """Validate reserve price"""
        reserve_price = self.cleaned_data.get('reserve_price')
        starting_price = self.cleaned_data.get('starting_price')
        auction_type = self.cleaned_data.get('auction_type')
        
        if auction_type == 'no_reserve' and reserve_price:
            raise ValidationError("No reserve auctions cannot have a reserve price.")
        
        if reserve_price and starting_price:
            if reserve_price < starting_price:
                raise ValidationError("Reserve price cannot be less than starting price.")
        
        return reserve_price
    
    def clean_buy_now_price(self):
        """Validate buy now price"""
        buy_now_price = self.cleaned_data.get('buy_now_price')
        reserve_price = self.cleaned_data.get('reserve_price')
        starting_price = self.cleaned_data.get('starting_price')
        
        if buy_now_price:
            if starting_price and buy_now_price < starting_price:
                raise ValidationError("Buy now price cannot be less than starting price.")
            
            if reserve_price and buy_now_price < reserve_price:
                raise ValidationError("Buy now price cannot be less than reserve price.")
        
        return buy_now_price
    
    def clean_deposit_amount(self):
        """Validate deposit amount"""
        deposit_amount = self.cleaned_data.get('deposit_amount')
        require_deposit = self.cleaned_data.get('require_deposit')
        
        if require_deposit and not deposit_amount:
            raise ValidationError("Deposit amount is required when deposit is mandatory.")
        
        if deposit_amount and deposit_amount < Decimal('0.01'):
            raise ValidationError("Deposit amount must be greater than zero.")
        
        return deposit_amount
    
    def clean_vehicle(self):
        """Validate vehicle selection"""
        vehicle = self.cleaned_data.get('vehicle')
        
        if vehicle:
            # Check if vehicle is already in an active auction
            existing_auction = Auction.objects.filter(
                vehicle=vehicle,
                status__in=['scheduled', 'active']
            ).exclude(pk=self.instance.pk if self.instance.pk else None).first()
            
            if existing_auction:
                raise ValidationError(
                    f"This vehicle is already in auction {existing_auction.auction_number}"
                )
        
        return vehicle
    
    def save(self, commit=True):
        """Save auction with additional data"""
        auction = super().save(commit=False)
        
        if self.user and not auction.created_by:
            auction.created_by = self.user
        
        # Set initial status for new auctions
        if not auction.pk:
            now = timezone.now()
            if auction.start_date <= now:
                auction.status = 'active'
            else:
                auction.status = 'scheduled'
        
        if commit:
            auction.save()
        
        return auction


class AuctionQuickCreateForm(forms.ModelForm):
    """
    Simplified form for quick auction creation
    """
    
    class Meta:
        model = Auction
        fields = [
            'vehicle',
            'starting_price',
            'start_date',
            'end_date',
        ]
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-control'}),
            'starting_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }


class AuctionSearchForm(forms.Form):
    """
    Form for searching and filtering auctions
    """
    
    STATUS_CHOICES = [('', 'All Statuses')] + list(Auction.STATUS_CHOICES)
    TYPE_CHOICES = [('', 'All Types')] + list(Auction.AUCTION_TYPE_CHOICES)
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search auctions...'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    auction_type = forms.ChoiceField(
        required=False,
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min price',
            'step': '0.01'
        })
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max price',
            'step': '0.01'
        })
    )
    featured_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# ============================================================================
# BID FORMS
# ============================================================================

class BidForm(forms.ModelForm):
    """
    Form for placing bids on auctions
    """
    
    class Meta:
        model = Bid
        fields = ['bid_amount']
        widgets = {
            'bid_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your bid',
                'step': '0.01',
                'min': '0.01'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.auction:
            # Set minimum bid
            min_bid = (
                self.auction.current_bid + self.auction.bid_increment
                if self.auction.current_bid > 0
                else self.auction.starting_price
            )
            
            self.fields['bid_amount'].widget.attrs['min'] = str(min_bid)
            self.fields['bid_amount'].help_text = f"Minimum bid: ${min_bid:,.2f}"
    
    def clean_bid_amount(self):
        """Validate bid amount"""
        bid_amount = self.cleaned_data.get('bid_amount')
        
        if not self.auction:
            raise ValidationError("Auction not specified.")
        
        # Check if auction is active
        if not self.auction.is_active:
            raise ValidationError("This auction is not currently active.")
        
        # Check minimum bid
        min_bid = (
            self.auction.current_bid + self.auction.bid_increment
            if self.auction.current_bid > 0
            else self.auction.starting_price
        )
        
        if bid_amount < min_bid:
            raise ValidationError(f"Minimum bid is ${min_bid:,.2f}")
        
        # Check if user is already highest bidder
        if self.user:
            latest_bid = self.auction.bids.filter(is_active=True).order_by('-bid_amount').first()
            if latest_bid and latest_bid.bidder == self.user:
                raise ValidationError("You are already the highest bidder.")
        
        # Check registration requirement
        if self.auction.require_registration and self.user:
            participant = AuctionParticipant.objects.filter(
                auction=self.auction,
                user=self.user,
                is_approved=True
            ).first()
            
            if not participant:
                raise ValidationError("You must be registered and approved to bid on this auction.")
        
        return bid_amount
    
    def save(self, commit=True):
        """Save bid with additional data"""
        bid = super().save(commit=False)
        
        if self.auction:
            bid.auction = self.auction
        
        if self.user:
            bid.bidder = self.user
        
        if commit:
            bid.save()
        
        return bid


class ProxyBidForm(forms.Form):
    """
    Form for setting up proxy bidding
    """
    
    max_bid_amount = forms.DecimalField(
        label="Maximum Bid Amount",
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter maximum bid',
            'step': '0.01'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        super().__init__(*args, **kwargs)
        
        if self.auction and not self.auction.allow_proxy_bidding:
            raise ValidationError("Proxy bidding is not allowed for this auction.")
    
    def clean_max_bid_amount(self):
        """Validate maximum bid amount"""
        max_bid = self.cleaned_data.get('max_bid_amount')
        
        if self.auction:
            min_bid = (
                self.auction.current_bid + self.auction.bid_increment
                if self.auction.current_bid > 0
                else self.auction.starting_price
            )
            
            if max_bid < min_bid:
                raise ValidationError(f"Maximum bid must be at least ${min_bid:,.2f}")
        
        return max_bid


class BuyNowForm(forms.Form):
    """
    Form for instant purchase at buy now price
    """
    
    confirm = forms.BooleanField(
        required=True,
        label="I confirm this purchase",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        super().__init__(*args, **kwargs)
        
        if self.auction and not self.auction.buy_now_price:
            raise ValidationError("Buy now is not available for this auction.")


# ============================================================================
# PARTICIPANT FORMS
# ============================================================================

class AuctionParticipantForm(forms.ModelForm):
    """
    Form for auction registration
    """
    
    agree_to_terms = forms.BooleanField(
        required=True,
        label="I agree to the auction terms and conditions",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = AuctionParticipant
        fields = [
            'client',
            'email_notifications',
            'sms_notifications',
            'proxy_bid_enabled',
            'proxy_max_amount',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'proxy_max_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional max bid',
                'step': '0.01'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter clients for current user
        if self.user:
            self.fields['client'].queryset = Client.objects.filter(user=self.user)
        
        # Proxy bidding fields only if allowed
        if self.auction and not self.auction.allow_proxy_bidding:
            self.fields['proxy_bid_enabled'].widget = forms.HiddenInput()
            self.fields['proxy_max_amount'].widget = forms.HiddenInput()
    
    def clean(self):
        """Validate participant registration"""
        cleaned_data = super().clean()
        
        # Check if already registered
        if self.auction and self.user:
            existing = AuctionParticipant.objects.filter(
                auction=self.auction,
                user=self.user
            ).first()
            
            if existing:
                raise ValidationError("You are already registered for this auction.")
        
        # Validate proxy bid
        proxy_enabled = cleaned_data.get('proxy_bid_enabled')
        proxy_max = cleaned_data.get('proxy_max_amount')
        
        if proxy_enabled and not proxy_max:
            raise ValidationError("Maximum bid amount required for proxy bidding.")
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save participant registration"""
        participant = super().save(commit=False)
        
        if self.auction:
            participant.auction = self.auction
        
        if self.user:
            participant.user = self.user
        
        # Auto-approve if registration doesn't require approval
        if not self.auction.require_registration:
            participant.is_approved = True
            participant.approved_at = timezone.now()
        
        if commit:
            participant.save()
        
        return participant


class ParticipantApprovalForm(forms.ModelForm):
    """
    Form for approving participant registrations
    """
    
    class Meta:
        model = AuctionParticipant
        fields = ['is_approved']
        widgets = {
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


# ============================================================================
# AUCTION RESULT FORMS
# ============================================================================

class AuctionResultForm(forms.ModelForm):
    """
    Form for creating and updating auction results
    """
    
    class Meta:
        model = AuctionResult
        fields = [
            'payment_status',
            'payment_due_date',
            'amount_paid',
            'delivery_status',
            'delivery_scheduled_date',
            'delivery_address',
            'buyers_premium',
            'taxes',
            'shipping_cost',
            'notes',
        ]
        widgets = {
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'payment_due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'delivery_status': forms.Select(attrs={'class': 'form-control'}),
            'delivery_scheduled_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'buyers_premium': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'taxes': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'shipping_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
        }


# ============================================================================
# WATCHLIST FORMS
# ============================================================================

class AddToWatchlistForm(forms.ModelForm):
    """
    Form for adding auction to watchlist
    """
    
    class Meta:
        model = AuctionWatchlist
        fields = ['notify_before_end', 'notify_on_outbid']
        widgets = {
            'notify_before_end': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_on_outbid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.auction = kwargs.pop('auction', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate watchlist addition"""
        cleaned_data = super().clean()
        
        if self.auction and self.user:
            # Check if already watching
            if AuctionWatchlist.objects.filter(
                auction=self.auction,
                user=self.user
            ).exists():
                raise ValidationError("You are already watching this auction.")
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save watchlist entry"""
        watchlist = super().save(commit=False)
        
        if self.auction:
            watchlist.auction = self.auction
        
        if self.user:
            watchlist.user = self.user
        
        if commit:
            watchlist.save()
        
        return watchlist