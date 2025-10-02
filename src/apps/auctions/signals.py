"""
Auctions App - Signal Handlers
"""

from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Max

from .models import Auction, Bid, AuctionParticipant, AuctionWatchlist, AuctionResult
from apps.vehicles.models import Vehicle
from apps.notifications.models import Notification
from apps.audit.models import AuditLog

User = get_user_model()


# ============================================================================
# AUCTION SIGNALS
# ============================================================================

@receiver(pre_save, sender=Auction)
def auction_pre_save(sender, instance, **kwargs):
    """Handle actions before auction is saved"""
    if instance.pk:
        try:
            old_instance = Auction.objects.get(pk=instance.pk)
            instance._previous_status = old_instance.status
            instance._previous_current_bid = old_instance.current_bid
        except Auction.DoesNotExist:
            pass


@receiver(post_save, sender=Auction)
def auction_post_save(sender, instance, created, **kwargs):
    """Handle actions after auction is saved"""
    if created:
        handle_new_auction(instance)
    else:
        handle_auction_update(instance)


def handle_new_auction(auction):
    """Handle new auction creation"""
    
    # Update vehicle status
    if auction.vehicle:
        auction.vehicle.status = 'in_auction'
        auction.vehicle.save(update_fields=['status'])
    
    # Notify staff/admins
    admin_users = User.objects.filter(is_staff=True, is_active=True)
    for admin in admin_users:
        Notification.objects.create(
            user=admin,
            title='New Auction Created',
            message=f'Auction {auction.auction_number} for {auction.vehicle} has been created',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='medium'
        )
    
    # Create audit log
    if auction.created_by:
        AuditLog.objects.create(
            user=auction.created_by,
            action='CREATE',
            model_name='Auction',
            object_id=auction.id,
            object_repr=str(auction),
            changes={
                'auction_number': auction.auction_number,
                'title': auction.title,
                'vehicle': str(auction.vehicle),
                'starting_price': str(auction.starting_price),
                'status': auction.status
            },
            ip_address=getattr(auction, '_ip_address', None)
        )


def handle_auction_update(auction):
    """Handle auction updates"""
    
    previous_status = getattr(auction, '_previous_status', None)
    
    if previous_status and previous_status != auction.status:
        handle_status_change(auction, previous_status)
    
    # Create audit log
    if hasattr(auction, '_changed_by'):
        AuditLog.objects.create(
            user=auction._changed_by,
            action='UPDATE',
            model_name='Auction',
            object_id=auction.id,
            object_repr=str(auction),
            changes={
                'previous_status': previous_status,
                'new_status': auction.status,
                'updated_at': str(timezone.now())
            },
            ip_address=getattr(auction, '_ip_address', None)
        )


def handle_status_change(auction, previous_status):
    """Handle auction status changes"""
    
    # Scheduled -> Active
    if auction.status == 'active' and previous_status == 'scheduled':
        notify_auction_started(auction)
    
    # Active -> Completed
    elif auction.status == 'completed' and previous_status == 'active':
        notify_auction_ended(auction)
        create_auction_result(auction)
    
    # Any -> Cancelled
    elif auction.status == 'cancelled':
        notify_auction_cancelled(auction)
        # Revert vehicle status
        if auction.vehicle:
            auction.vehicle.status = 'available'
            auction.vehicle.save(update_fields=['status'])


def notify_auction_started(auction):
    """Notify participants when auction starts"""
    
    participants = auction.participants.filter(is_approved=True, email_notifications=True)
    for participant in participants:
        Notification.objects.create(
            user=participant.user,
            title='Auction Started',
            message=f'Auction {auction.auction_number} for {auction.vehicle} has started!',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='high'
        )
    
    # Notify watchers
    watchers = auction.watchers.all()
    for watcher in watchers:
        Notification.objects.create(
            user=watcher.user,
            title='Watched Auction Started',
            message=f'Auction {auction.auction_number} you are watching has started',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='medium'
        )


def notify_auction_ended(auction):
    """Notify participants when auction ends"""
    
    # Notify winner
    if auction.winner:
        Notification.objects.create(
            user=auction.winner,
            title='Congratulations! You Won!',
            message=f'You won auction {auction.auction_number} for {auction.vehicle} with a bid of ${auction.winning_bid_amount:,.2f}',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='urgent'
        )
    
    # Notify all participants
    participants = auction.participants.filter(is_approved=True)
    for participant in participants:
        if participant.user != auction.winner:
            Notification.objects.create(
                user=participant.user,
                title='Auction Ended',
                message=f'Auction {auction.auction_number} has ended. {"Reserve not met." if not auction.reserve_met else ""}',
                notification_type='auction',
                related_object_type='auction',
                related_object_id=auction.id,
                priority='medium'
            )
    
    # Notify watchers
    watchers = auction.watchers.all()
    for watcher in watchers:
        if watcher.user != auction.winner:
            Notification.objects.create(
                user=watcher.user,
                title='Watched Auction Ended',
                message=f'Auction {auction.auction_number} has ended',
                notification_type='auction',
                related_object_type='auction',
                related_object_id=auction.id,
                priority='low'
            )


def notify_auction_cancelled(auction):
    """Notify participants when auction is cancelled"""
    
    participants = auction.participants.filter(is_approved=True)
    for participant in participants:
        Notification.objects.create(
            user=participant.user,
            title='Auction Cancelled',
            message=f'Auction {auction.auction_number} has been cancelled',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='high'
        )
    
    watchers = auction.watchers.all()
    for watcher in watchers:
        Notification.objects.create(
            user=watcher.user,
            title='Watched Auction Cancelled',
            message=f'Auction {auction.auction_number} you were watching has been cancelled',
            notification_type='auction',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='medium'
        )


def create_auction_result(auction):
    """Create auction result record"""
    
    if auction.winner and auction.winning_bid_amount:
        winning_bid = auction.bids.filter(is_winning_bid=True).first()
        
        # Calculate payment due date (e.g., 7 days from now)
        payment_due = timezone.now() + timezone.timedelta(days=7)
        
        AuctionResult.objects.get_or_create(
            auction=auction,
            defaults={
                'winner': auction.winner,
                'winning_bid': winning_bid,
                'final_price': auction.winning_bid_amount,
                'payment_due_date': payment_due,
                'payment_status': 'pending',
                'delivery_status': 'pending',
                'buyers_premium': auction.winning_bid_amount * 0.05,  # 5% premium
                'total_amount': auction.winning_bid_amount * 1.05
            }
        )


@receiver(post_delete, sender=Auction)
def auction_post_delete(sender, instance, **kwargs):
    """Handle actions after auction is deleted"""
    
    # Revert vehicle status
    if instance.vehicle:
        instance.vehicle.status = 'available'
        instance.vehicle.save(update_fields=['status'])
    
    # Create audit log
    if hasattr(instance, '_deleted_by'):
        AuditLog.objects.create(
            user=instance._deleted_by,
            action='DELETE',
            model_name='Auction',
            object_id=instance.id,
            object_repr=str(instance),
            changes={
                'auction_number': instance.auction_number,
                'vehicle': str(instance.vehicle),
                'status': instance.status,
                'deleted_at': str(timezone.now())
            },
            ip_address=getattr(instance, '_ip_address', None)
        )


# ============================================================================
# BID SIGNALS
# ============================================================================

@receiver(post_save, sender=Bid)
def bid_post_save(sender, instance, created, **kwargs):
    """Handle actions after bid is saved"""
    
    if created:
        handle_new_bid(instance)


def handle_new_bid(bid):
    """Handle new bid placement"""
    
    auction = bid.auction
    
    # Notify previous highest bidder (outbid notification)
    previous_highest = Bid.objects.filter(
        auction=auction,
        is_active=True,
        is_outbid=True
    ).order_by('-bid_amount').first()
    
    if previous_highest and previous_highest.bidder != bid.bidder:
        Notification.objects.create(
            user=previous_highest.bidder,
            title='You Have Been Outbid',
            message=f'Your bid on {auction.vehicle} has been outbid. Current bid: ${bid.bid_amount:,.2f}',
            notification_type='bid',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='high'
        )
    
    # Notify watchers
    watchers = auction.watchers.filter(notify_on_outbid=True).exclude(user=bid.bidder)
    for watcher in watchers:
        Notification.objects.create(
            user=watcher.user,
            title='New Bid on Watched Auction',
            message=f'New bid of ${bid.bid_amount:,.2f} placed on {auction.vehicle}',
            notification_type='bid',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='medium'
        )
    
    # Notify auction creator/staff
    if auction.created_by and auction.created_by != bid.bidder:
        Notification.objects.create(
            user=auction.created_by,
            title='New Bid Received',
            message=f'New bid of ${bid.bid_amount:,.2f} on auction {auction.auction_number}',
            notification_type='bid',
            related_object_type='auction',
            related_object_id=auction.id,
            priority='low'
        )
    
    # Check if reserve price met (first time)
    if auction.reserve_price and not auction.reserve_met:
        if bid.bid_amount >= auction.reserve_price:
            auction.reserve_met = True
            auction.save(update_fields=['reserve_met'])
            
            # Notify bidder
            Notification.objects.create(
                user=bid.bidder,
                title='Reserve Price Met',
                message=f'Your bid meets the reserve price for {auction.vehicle}',
                notification_type='bid',
                related_object_type='auction',
                related_object_id=auction.id,
                priority='high'
            )
    
    # Create audit log
    AuditLog.objects.create(
        user=bid.bidder,
        action='CREATE',
        model_name='Bid',
        object_id=bid.id,
        object_repr=str(bid),
        changes={
            'auction': str(auction),
            'bid_amount': str(bid.bid_amount),
            'bid_type': bid.bid_type
        },
        ip_address=bid.ip_address
    )


# ============================================================================
# PARTICIPANT SIGNALS
# ============================================================================

@receiver(post_save, sender=AuctionParticipant)
def participant_post_save(sender, instance, created, **kwargs):
    """Handle actions after participant registration"""
    
    if created:
        # Notify participant
        Notification.objects.create(
            user=instance.user,
            title='Auction Registration Received',
            message=f'Your registration for auction {instance.auction.auction_number} has been received',
            notification_type='registration',
            related_object_type='auction',
            related_object_id=instance.auction.id,
            priority='medium'
        )
        
        # Notify auction creator/staff
        if instance.auction.created_by:
            Notification.objects.create(
                user=instance.auction.created_by,
                title='New Auction Registration',
                message=f'{instance.user.get_full_name()} registered for auction {instance.auction.auction_number}',
                notification_type='registration',
                related_object_type='auction',
                related_object_id=instance.auction.id,
                priority='low'
            )
    
    # If approved
    if instance.is_approved and hasattr(instance, '_just_approved'):
        Notification.objects.create(
            user=instance.user,
            title='Auction Registration Approved',
            message=f'You have been approved to bid on auction {instance.auction.auction_number}',
            notification_type='registration',
            related_object_type='auction',
            related_object_id=instance.auction.id,
            priority='high'
        )


# ============================================================================
# WATCHLIST SIGNALS
# ============================================================================

@receiver(post_save, sender=AuctionWatchlist)
def watchlist_post_save(sender, instance, created, **kwargs):
    """Handle actions after watchlist addition"""
    
    if created:
        # Increment watchers count done in view
        pass


@receiver(post_delete, sender=AuctionWatchlist)
def watchlist_post_delete(sender, instance, **kwargs):
    """Handle actions after watchlist removal"""
    # Decrement watchers count done in view
    pass


# ============================================================================
# AUCTION RESULT SIGNALS
# ============================================================================

@receiver(post_save, sender=AuctionResult)
def result_post_save(sender, instance, created, **kwargs):
    """Handle actions after result is saved"""
    
    if created:
        # Update vehicle status
        if instance.auction.vehicle:
            instance.auction.vehicle.status = 'sold'
            instance.auction.vehicle.save(update_fields=['status'])
    
    # Check payment status change
    if hasattr(instance, '_previous_payment_status'):
        if instance.payment_status == 'paid' and instance._previous_payment_status != 'paid':
            Notification.objects.create(
                user=instance.winner,
                title='Payment Confirmed',
                message=f'Your payment for auction {instance.auction.auction_number} has been confirmed',
                notification_type='payment',
                related_object_type='auction',
                related_object_id=instance.auction.id,
                priority='high'
            )
    
    # Check delivery status change
    if hasattr(instance, '_previous_delivery_status'):
        if instance.delivery_status == 'delivered' and instance._previous_delivery_status != 'delivered':
            Notification.objects.create(
                user=instance.winner,
                title='Vehicle Delivered',
                message=f'Your vehicle from auction {instance.auction.auction_number} has been delivered',
                notification_type='delivery',
                related_object_type='auction',
                related_object_id=instance.auction.id,
                priority='high'
            )


@receiver(pre_save, sender=AuctionResult)
def result_pre_save(sender, instance, **kwargs):
    """Track previous values before save"""
    if instance.pk:
        try:
            old_instance = AuctionResult.objects.get(pk=instance.pk)
            instance._previous_payment_status = old_instance.payment_status
            instance._previous_delivery_status = old_instance.delivery_status
        except AuctionResult.DoesNotExist:
            pass


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def check_auction_endings():
    """
    Check for auctions ending soon and send notifications
    Should be called from scheduled task (Celery beat)
    """
    
    # Auctions ending in 1 hour
    one_hour_from_now = timezone.now() + timezone.timedelta(hours=1)
    ending_soon = Auction.objects.filter(
        status='active',
        end_date__lte=one_hour_from_now,
        end_date__gt=timezone.now()
    )
    
    for auction in ending_soon:
        # Notify participants
        participants = auction.participants.filter(is_approved=True, email_notifications=True)
        for participant in participants:
            Notification.objects.create(
                user=participant.user,
                title='Auction Ending Soon',
                message=f'Auction {auction.auction_number} ends in less than 1 hour!',
                notification_type='auction',
                related_object_type='auction',
                related_object_id=auction.id,
                priority='high'
            )
        
        # Notify watchers
        watchers = auction.watchers.filter(notify_before_end=True)
        for watcher in watchers:
            Notification.objects.create(
                user=watcher.user,
                title='Watched Auction Ending Soon',
                message=f'Auction {auction.auction_number} ends in less than 1 hour',
                notification_type='auction',
                related_object_type='auction',
                related_object_id=auction.id,
                priority='medium'
            )


def auto_finalize_expired_auctions():
    """
    Automatically finalize expired auctions
    Should be called from scheduled task (Celery beat)
    """
    
    expired_auctions = Auction.objects.filter(
        status='active',
        end_date__lt=timezone.now()
    )
    
    for auction in expired_auctions:
        auction.finalize_auction()


def send_payment_reminders():
    """
    Send payment reminders for overdue results
    Should be called from scheduled task (Celery beat)
    """
    
    overdue_results = AuctionResult.objects.filter(
        payment_status='pending',
        payment_due_date__lt=timezone.now()
    )
    
    for result in overdue_results:
        if result.winner:
            Notification.objects.create(
                user=result.winner,
                title='Payment Overdue',
                message=f'Payment for auction {result.auction.auction_number} is overdue. Please complete payment.',
                notification_type='payment',
                related_object_type='auction',
                related_object_id=result.auction.id,
                priority='urgent'
            )