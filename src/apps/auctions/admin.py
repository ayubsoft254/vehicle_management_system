"""
Auctions App - Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Max, Sum
from django.contrib import messages

from .models import (
    Auction,
    Bid,
    AuctionParticipant,
    AuctionWatchlist,
    AuctionResult
)


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ['bidder', 'bid_amount', 'bid_type', 'created_at', 'is_winning_bid', 'is_outbid']
    can_delete = False
    max_num = 10
    ordering = ['-bid_amount', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


class AuctionParticipantInline(admin.TabularInline):
    model = AuctionParticipant
    extra = 0
    readonly_fields = ['user', 'registered_at', 'total_bids', 'highest_bid']
    fields = ['user', 'is_approved', 'registration_fee_paid', 'deposit_paid', 'total_bids', 'highest_bid']
    can_delete = False


class AuctionResultInline(admin.StackedInline):
    model = AuctionResult
    extra = 0
    readonly_fields = ['winner', 'winning_bid', 'final_price', 'total_amount', 'created_at']
    fieldsets = (
        ('Winner Information', {
            'fields': ('winner', 'winning_bid', 'final_price')
        }),
        ('Payment Details', {
            'fields': ('payment_status', 'payment_due_date', 'amount_paid', 'payment_completed_at')
        }),
        ('Delivery Details', {
            'fields': ('delivery_status', 'delivery_scheduled_date', 'delivery_address', 'delivery_completed_date')
        }),
        ('Additional Costs', {
            'fields': ('buyers_premium', 'taxes', 'shipping_cost', 'total_amount')
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = [
        'auction_number',
        'title',
        'vehicle_link',
        'status_badge',
        'auction_type',
        'current_bid_display',
        'total_bids',
        'unique_bidders',
        'start_date',
        'end_date',
        'featured',
        'created_at'
    ]
    list_filter = [
        'status',
        'auction_type',
        'featured',
        'require_registration',
        'allow_proxy_bidding',
        'created_at',
        'start_date',
        'end_date'
    ]
    search_fields = [
        'auction_number',
        'title',
        'vehicle__vin',
        'vehicle__make',
        'vehicle__model',
        'description'
    ]
    readonly_fields = [
        'auction_number',
        'current_bid',
        'total_bids',
        'unique_bidders',
        'winner',
        'winning_bid_amount',
        'reserve_met',
        'views_count',
        'watchers_count',
        'created_by',
        'created_at',
        'updated_at',
        'completed_at',
        'time_remaining_display',
        'reserve_status_display'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'auction_number',
                'title',
                'description',
                'auction_type',
                'status',
                'vehicle'
            )
        }),
        ('Pricing', {
            'fields': (
                'starting_price',
                'reserve_price',
                'current_bid',
                'bid_increment',
                'buy_now_price',
                'reserve_status_display'
            )
        }),
        ('Schedule', {
            'fields': (
                'start_date',
                'end_date',
                'extended_end_date',
                'time_remaining_display'
            )
        }),
        ('Bidding Configuration', {
            'fields': (
                'allow_proxy_bidding',
                'auto_extend',
                'extension_minutes',
                'minimum_bidders'
            )
        }),
        ('Participation Requirements', {
            'fields': (
                'require_registration',
                'registration_fee',
                'require_deposit',
                'deposit_amount'
            )
        }),
        ('Results', {
            'fields': (
                'winner',
                'winning_bid_amount',
                'reserve_met',
                'total_bids',
                'unique_bidders'
            )
        }),
        ('Additional Settings', {
            'fields': (
                'terms_and_conditions',
                'inspection_available',
                'inspection_location',
                'featured'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'views_count',
                'watchers_count'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
                'completed_at'
            ),
            'classes': ('collapse',)
        })
    )
    inlines = [AuctionParticipantInline, BidInline, AuctionResultInline]
    date_hierarchy = 'start_date'
    list_per_page = 25
    actions = [
        'mark_as_active',
        'mark_as_completed',
        'mark_as_cancelled',
        'finalize_selected_auctions',
        'feature_auctions',
        'unfeature_auctions'
    ]
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('vehicle', 'created_by', 'winner')
        queryset = queryset.annotate(
            bid_count=Count('bids'),
            latest_bid=Max('bids__bid_amount')
        )
        return queryset
    
    def vehicle_link(self, obj):
        if obj.vehicle:
            url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.pk])
            return format_html('<a href="{}">{}</a>', url, obj.vehicle)
        return '-'
    vehicle_link.short_description = 'Vehicle'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'scheduled': 'blue',
            'active': 'green',
            'completed': 'purple',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def current_bid_display(self, obj):
        if obj.current_bid > 0:
            return format_html('${:,.2f}', obj.current_bid)
        return format_html('<span style="color: gray;">No bids</span>')
    current_bid_display.short_description = 'Current Bid'
    current_bid_display.admin_order_field = 'current_bid'
    
    def time_remaining_display(self, obj):
        if obj.is_active:
            remaining = obj.time_remaining
            if remaining:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return format_html(
                    '<span style="color: green; font-weight: bold;">{}h {}m</span>',
                    hours, minutes
                )
        elif obj.status == 'scheduled':
            return format_html('<span style="color: blue;">Not started</span>')
        elif obj.status == 'completed':
            return format_html('<span style="color: gray;">Ended</span>')
        return '-'
    time_remaining_display.short_description = 'Time Remaining'
    
    def reserve_status_display(self, obj):
        status = obj.reserve_status
        if status == 'no_reserve':
            return format_html('<span style="color: green;">No Reserve</span>')
        elif status == 'reserve_met':
            return format_html('<span style="color: green;">✓ Reserve Met</span>')
        else:
            return format_html('<span style="color: orange;">Reserve Not Met</span>')
    reserve_status_display.short_description = 'Reserve Status'
    
    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} auction(s) marked as active.', messages.SUCCESS)
    mark_as_active.short_description = 'Mark selected as Active'
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} auction(s) marked as completed.', messages.SUCCESS)
    mark_as_completed.short_description = 'Mark selected as Completed'
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} auction(s) marked as cancelled.', messages.SUCCESS)
    mark_as_cancelled.short_description = 'Mark selected as Cancelled'
    
    def finalize_selected_auctions(self, request, queryset):
        count = 0
        for auction in queryset.filter(status='active'):
            auction.finalize_auction()
            count += 1
        self.message_user(request, f'{count} auction(s) finalized.', messages.SUCCESS)
    finalize_selected_auctions.short_description = 'Finalize selected auctions'
    
    def feature_auctions(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f'{updated} auction(s) featured.', messages.SUCCESS)
    feature_auctions.short_description = 'Feature selected auctions'
    
    def unfeature_auctions(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(request, f'{updated} auction(s) unfeatured.', messages.SUCCESS)
    unfeature_auctions.short_description = 'Unfeature selected auctions'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'auction_link',
        'bidder_link',
        'bid_amount_display',
        'bid_type',
        'is_winning_bid',
        'is_outbid',
        'created_at'
    ]
    list_filter = [
        'bid_type',
        'is_winning_bid',
        'is_outbid',
        'is_active',
        'created_at'
    ]
    search_fields = [
        'auction__auction_number',
        'auction__title',
        'bidder__username',
        'bidder__email',
        'bidder__first_name',
        'bidder__last_name'
    ]
    readonly_fields = [
        'auction',
        'bidder',
        'bid_amount',
        'bid_type',
        'is_active',
        'is_winning_bid',
        'is_outbid',
        'created_at',
        'ip_address',
        'user_agent'
    ]
    date_hierarchy = 'created_at'
    list_per_page = 50
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def auction_link(self, obj):
        url = reverse('admin:auctions_auction_change', args=[obj.auction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.auction.auction_number)
    auction_link.short_description = 'Auction'
    
    def bidder_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.bidder.pk])
        return format_html('<a href="{}">{}</a>', url, obj.bidder.get_full_name() or obj.bidder.username)
    bidder_link.short_description = 'Bidder'
    
    def bid_amount_display(self, obj):
        color = 'green' if obj.is_winning_bid else 'black'
        return format_html('<span style="color: {}; font-weight: bold;">${:,.2f}</span>', color, obj.bid_amount)
    bid_amount_display.short_description = 'Bid Amount'
    bid_amount_display.admin_order_field = 'bid_amount'


@admin.register(AuctionParticipant)
class AuctionParticipantAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'auction_link',
        'registered_at',
        'is_approved',
        'registration_fee_paid',
        'deposit_paid',
        'total_bids',
        'highest_bid_display',
        'proxy_bid_enabled'
    ]
    list_filter = [
        'is_approved',
        'registration_fee_paid',
        'deposit_paid',
        'deposit_refunded',
        'proxy_bid_enabled',
        'registered_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'auction__auction_number',
        'auction__title'
    ]
    readonly_fields = [
        'registered_at',
        'approved_at',
        'total_bids',
        'highest_bid'
    ]
    fieldsets = (
        ('Participant Information', {
            'fields': ('auction', 'user', 'client')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approved_by', 'approved_at')
        }),
        ('Financial', {
            'fields': (
                'registration_fee_paid',
                'deposit_paid',
                'deposit_amount',
                'deposit_refunded'
            )
        }),
        ('Bidding', {
            'fields': (
                'total_bids',
                'highest_bid',
                'proxy_bid_enabled',
                'proxy_max_amount'
            )
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'sms_notifications')
        }),
        ('Metadata', {
            'fields': ('registered_at',)
        })
    )
    date_hierarchy = 'registered_at'
    actions = ['approve_participants', 'mark_fees_paid', 'mark_deposit_paid']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def auction_link(self, obj):
        url = reverse('admin:auctions_auction_change', args=[obj.auction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.auction.auction_number)
    auction_link.short_description = 'Auction'
    
    def highest_bid_display(self, obj):
        if obj.highest_bid:
            return format_html('${:,.2f}', obj.highest_bid)
        return '-'
    highest_bid_display.short_description = 'Highest Bid'
    highest_bid_display.admin_order_field = 'highest_bid'
    
    def approve_participants(self, request, queryset):
        for participant in queryset:
            participant.approve(request.user)
        self.message_user(request, f'{queryset.count()} participant(s) approved.', messages.SUCCESS)
    approve_participants.short_description = 'Approve selected participants'
    
    def mark_fees_paid(self, request, queryset):
        updated = queryset.update(registration_fee_paid=True)
        self.message_user(request, f'{updated} participant(s) marked as fee paid.', messages.SUCCESS)
    mark_fees_paid.short_description = 'Mark registration fees as paid'
    
    def mark_deposit_paid(self, request, queryset):
        updated = queryset.update(deposit_paid=True)
        self.message_user(request, f'{updated} participant(s) marked as deposit paid.', messages.SUCCESS)
    mark_deposit_paid.short_description = 'Mark deposits as paid'


@admin.register(AuctionWatchlist)
class AuctionWatchlistAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'auction_link',
        'added_at',
        'notify_before_end',
        'notify_on_outbid'
    ]
    list_filter = [
        'notify_before_end',
        'notify_on_outbid',
        'added_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'auction__auction_number',
        'auction__title'
    ]
    readonly_fields = ['added_at']
    date_hierarchy = 'added_at'
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def auction_link(self, obj):
        url = reverse('admin:auctions_auction_change', args=[obj.auction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.auction.auction_number)
    auction_link.short_description = 'Auction'


@admin.register(AuctionResult)
class AuctionResultAdmin(admin.ModelAdmin):
    list_display = [
        'auction_link',
        'winner_link',
        'final_price_display',
        'total_amount_display',
        'payment_status',
        'delivery_status',
        'payment_progress_bar',
        'created_at'
    ]
    list_filter = [
        'payment_status',
        'delivery_status',
        'created_at'
    ]
    search_fields = [
        'auction__auction_number',
        'auction__title',
        'winner__username',
        'winner__email'
    ]
    readonly_fields = [
        'auction',
        'winner',
        'winning_bid',
        'final_price',
        'total_amount',
        'payment_progress',
        'is_payment_overdue',
        'created_at',
        'updated_at'
    ]
    fieldsets = (
        ('Auction Information', {
            'fields': ('auction', 'winner', 'winning_bid', 'final_price')
        }),
        ('Payment Details', {
            'fields': (
                'payment_status',
                'payment_due_date',
                'amount_paid',
                'payment_completed_at',
                'payment_progress',
                'is_payment_overdue'
            )
        }),
        ('Delivery Details', {
            'fields': (
                'delivery_status',
                'delivery_scheduled_date',
                'delivery_address',
                'delivery_completed_date'
            )
        }),
        ('Additional Costs', {
            'fields': (
                'buyers_premium',
                'taxes',
                'shipping_cost',
                'total_amount'
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'created_at'
    actions = ['mark_payment_complete', 'mark_delivered']
    
    def auction_link(self, obj):
        url = reverse('admin:auctions_auction_change', args=[obj.auction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.auction.auction_number)
    auction_link.short_description = 'Auction'
    
    def winner_link(self, obj):
        if obj.winner:
            url = reverse('admin:auth_user_change', args=[obj.winner.pk])
            return format_html('<a href="{}">{}</a>', url, obj.winner.get_full_name() or obj.winner.username)
        return '-'
    winner_link.short_description = 'Winner'
    
    def final_price_display(self, obj):
        return format_html('${:,.2f}', obj.final_price)
    final_price_display.short_description = 'Final Price'
    final_price_display.admin_order_field = 'final_price'
    
    def total_amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.total_amount)
    total_amount_display.short_description = 'Total Amount'
    total_amount_display.admin_order_field = 'total_amount'
    
    def payment_progress_bar(self, obj):
        progress = obj.payment_progress
        color = 'green' if progress >= 100 else 'orange' if progress >= 50 else 'red'
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 11px; line-height: 20px;">'
            '{}%'
            '</div></div>',
            min(progress, 100), color, int(progress)
        )
    payment_progress_bar.short_description = 'Payment Progress'
    
    def mark_payment_complete(self, request, queryset):
        updated = queryset.update(
            payment_status='paid',
            payment_completed_at=timezone.now()
        )
        self.message_user(request, f'{updated} result(s) marked as paid.', messages.SUCCESS)
    mark_payment_complete.short_description = 'Mark payment as complete'
    
    def mark_delivered(self, request, queryset):
        updated = queryset.update(
            delivery_status='delivered',
            delivery_completed_date=timezone.now()
        )
        self.message_user(request, f'{updated} result(s) marked as delivered.', messages.SUCCESS)
    mark_delivered.short_description = 'Mark as delivered'