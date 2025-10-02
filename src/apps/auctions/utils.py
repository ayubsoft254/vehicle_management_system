"""
Auctions App - Utility Functions
"""

from django.utils import timezone
from django.db.models import Count, Max, Min, Avg, Sum, Q
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import random
import string

from .models import Auction, Bid, AuctionParticipant, AuctionResult


# ============================================================================
# AUCTION NUMBER GENERATION
# ============================================================================

def generate_auction_number(prefix='AUC'):
    """Generate unique auction number"""
    date_part = timezone.now().strftime('%Y%m%d')
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = Auction.objects.filter(created_at__gte=today_start).count() + 1
    return f"{prefix}-{date_part}-{count:04d}"


def generate_random_code(length=8):
    """Generate random alphanumeric code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


# ============================================================================
# AUCTION STATISTICS
# ============================================================================

def get_auction_statistics(auction):
    """Get comprehensive statistics for an auction"""
    
    bids = auction.bids.all()
    
    stats = {
        'total_bids': bids.count(),
        'unique_bidders': bids.values('bidder').distinct().count(),
        'average_bid': bids.aggregate(avg=Avg('bid_amount'))['avg'] or Decimal('0.00'),
        'highest_bid': bids.aggregate(max=Max('bid_amount'))['max'] or Decimal('0.00'),
        'lowest_bid': bids.aggregate(min=Min('bid_amount'))['min'] or Decimal('0.00'),
        'total_value': bids.aggregate(sum=Sum('bid_amount'))['sum'] or Decimal('0.00'),
        'views_count': auction.views_count,
        'watchers_count': auction.watchers_count,
        'participants_count': auction.participants.filter(is_approved=True).count(),
        'bid_increment_avg': Decimal('0.00'),
        'time_between_bids': None,
        'most_active_bidder': None,
        'bid_activity_by_hour': {},
    }
    
    # Calculate average bid increment
    if bids.count() > 1:
        bid_list = list(bids.order_by('created_at').values_list('bid_amount', flat=True))
        increments = [bid_list[i] - bid_list[i-1] for i in range(1, len(bid_list))]
        if increments:
            stats['bid_increment_avg'] = sum(increments) / len(increments)
    
    # Time between bids
    if bids.count() > 1:
        first_bid = bids.order_by('created_at').first()
        last_bid = bids.order_by('created_at').last()
        time_diff = last_bid.created_at - first_bid.created_at
        stats['time_between_bids'] = time_diff / (bids.count() - 1) if bids.count() > 1 else None
    
    # Most active bidder
    bidder_counts = bids.values('bidder__username').annotate(
        count=Count('id')
    ).order_by('-count').first()
    
    if bidder_counts:
        stats['most_active_bidder'] = {
            'username': bidder_counts['bidder__username'],
            'bid_count': bidder_counts['count']
        }
    
    # Bid activity by hour
    for bid in bids:
        hour = bid.created_at.hour
        stats['bid_activity_by_hour'][hour] = stats['bid_activity_by_hour'].get(hour, 0) + 1
    
    return stats


def get_bidder_statistics(user):
    """Get bidding statistics for a user"""
    
    bids = Bid.objects.filter(bidder=user)
    
    stats = {
        'total_bids': bids.count(),
        'total_auctions': bids.values('auction').distinct().count(),
        'winning_bids': bids.filter(is_winning_bid=True).count(),
        'active_bids': bids.filter(auction__status='active', is_active=True).count(),
        'total_spent': AuctionResult.objects.filter(
            winner=user,
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'average_bid': bids.aggregate(avg=Avg('bid_amount'))['avg'] or Decimal('0.00'),
        'highest_bid': bids.aggregate(max=Max('bid_amount'))['max'] or Decimal('0.00'),
        'success_rate': 0,
    }
    
    # Calculate success rate
    if stats['total_auctions'] > 0:
        stats['success_rate'] = (stats['winning_bids'] / stats['total_auctions']) * 100
    
    return stats


def get_auction_performance_metrics():
    """Get overall auction platform performance metrics"""
    
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    
    metrics = {
        'total_auctions': Auction.objects.count(),
        'active_auctions': Auction.objects.filter(status='active').count(),
        'completed_auctions': Auction.objects.filter(status='completed').count(),
        'total_bids': Bid.objects.count(),
        'total_participants': AuctionParticipant.objects.filter(is_approved=True).count(),
        'total_revenue': AuctionResult.objects.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'average_auction_price': AuctionResult.objects.aggregate(
            avg=Avg('final_price')
        )['avg'] or Decimal('0.00'),
        'completion_rate': 0,
        'last_30_days': {
            'auctions': Auction.objects.filter(created_at__gte=thirty_days_ago).count(),
            'bids': Bid.objects.filter(created_at__gte=thirty_days_ago).count(),
            'revenue': AuctionResult.objects.filter(
                created_at__gte=thirty_days_ago,
                payment_status='paid'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        }
    }
    
    # Calculate completion rate
    total = Auction.objects.count()
    if total > 0:
        completed = Auction.objects.filter(status='completed').count()
        metrics['completion_rate'] = (completed / total) * 100
    
    return metrics


# ============================================================================
# AUCTION VALIDATION
# ============================================================================

def validate_bid_amount(auction, bid_amount, user):
    """Validate if a bid amount is valid for an auction"""
    
    errors = []
    
    # Check if auction is active
    if not auction.is_active:
        errors.append('Auction is not currently active')
    
    # Check minimum bid
    min_bid = auction.current_bid + auction.bid_increment if auction.current_bid > 0 else auction.starting_price
    if bid_amount < min_bid:
        errors.append(f'Minimum bid is ${min_bid:,.2f}')
    
    # Check if user is current highest bidder
    latest_bid = auction.bids.filter(is_active=True).order_by('-bid_amount').first()
    if latest_bid and latest_bid.bidder == user:
        errors.append('You are already the highest bidder')
    
    # Check registration requirement
    if auction.require_registration:
        if not AuctionParticipant.objects.filter(
            auction=auction,
            user=user,
            is_approved=True
        ).exists():
            errors.append('You must be registered and approved for this auction')
    
    return len(errors) == 0, errors


def can_user_bid(auction, user):
    """Check if user can bid on an auction"""
    
    if not user.is_authenticated:
        return False, 'You must be logged in to bid'
    
    if not auction.is_active:
        return False, 'Auction is not active'
    
    if auction.require_registration:
        participant = AuctionParticipant.objects.filter(
            auction=auction,
            user=user,
            is_approved=True
        ).first()
        
        if not participant:
            return False, 'You must be registered and approved'
        
        if auction.require_deposit and not participant.deposit_paid:
            return False, 'Deposit payment required'
    
    return True, 'Authorized to bid'


# ============================================================================
# AUCTION TIMING
# ============================================================================

def calculate_time_remaining(auction):
    """Calculate time remaining in auction"""
    
    if not auction.is_active:
        return None
    
    remaining = auction.end_date - timezone.now()
    
    if remaining.total_seconds() <= 0:
        return timedelta(seconds=0)
    
    return remaining


def format_time_remaining(time_delta):
    """Format time delta to human-readable string"""
    
    if not time_delta:
        return 'Ended'
    
    total_seconds = int(time_delta.total_seconds())
    
    if total_seconds <= 0:
        return 'Ended'
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    if days > 0:
        return f'{days}d {hours}h {minutes}m'
    elif hours > 0:
        return f'{hours}h {minutes}m'
    else:
        return f'{minutes}m'


def is_auction_ending_soon(auction, threshold_minutes=60):
    """Check if auction is ending within threshold"""
    
    if not auction.is_active:
        return False
    
    remaining = calculate_time_remaining(auction)
    if not remaining:
        return False
    
    return remaining.total_seconds() <= (threshold_minutes * 60)


# ============================================================================
# BID CALCULATIONS
# ============================================================================

def calculate_next_minimum_bid(auction):
    """Calculate the next minimum bid amount"""
    
    if auction.current_bid > 0:
        return auction.current_bid + auction.bid_increment
    return auction.starting_price


def calculate_proxy_bid(auction, max_amount, current_highest):
    """Calculate proxy bid amount based on max and current highest"""
    
    if current_highest >= max_amount:
        return None  # Can't outbid with proxy
    
    # Bid just enough to win
    next_bid = current_highest + auction.bid_increment
    
    if next_bid > max_amount:
        return max_amount
    
    return next_bid


def apply_buyers_premium(final_price, premium_percentage=5.0):
    """Calculate buyer's premium"""
    
    premium = final_price * (Decimal(str(premium_percentage)) / Decimal('100'))
    return final_price + premium


def calculate_total_auction_cost(final_price, premium_percentage=5.0, tax_rate=0.0, shipping=Decimal('0.00')):
    """Calculate total cost including all fees"""
    
    premium = final_price * (Decimal(str(premium_percentage)) / Decimal('100'))
    subtotal = final_price + premium
    tax = subtotal * Decimal(str(tax_rate))
    total = subtotal + tax + shipping
    
    return {
        'final_price': final_price,
        'buyers_premium': premium,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total
    }


# ============================================================================
# EMAIL NOTIFICATIONS
# ============================================================================

def send_auction_email(to_email, subject, template_name, context):
    """Send auction-related email"""
    
    html_message = render_to_string(f'auctions/emails/{template_name}.html', context)
    plain_message = render_to_string(f'auctions/emails/{template_name}.txt', context)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        html_message=html_message,
        fail_silently=False
    )


def send_bid_confirmation_email(bid):
    """Send bid confirmation email"""
    
    context = {
        'bid': bid,
        'auction': bid.auction,
        'user': bid.bidder
    }
    
    send_auction_email(
        to_email=bid.bidder.email,
        subject=f'Bid Confirmation - Auction {bid.auction.auction_number}',
        template_name='bid_confirmation',
        context=context
    )


def send_winning_notification_email(auction):
    """Send winning notification to auction winner"""
    
    if not auction.winner:
        return
    
    context = {
        'auction': auction,
        'user': auction.winner,
        'winning_amount': auction.winning_bid_amount
    }
    
    send_auction_email(
        to_email=auction.winner.email,
        subject=f'Congratulations! You won - {auction.title}',
        template_name='winner_notification',
        context=context
    )


def send_outbid_notification_email(bid, new_bid):
    """Send outbid notification"""
    
    context = {
        'bid': bid,
        'new_bid': new_bid,
        'auction': bid.auction,
        'user': bid.bidder
    }
    
    send_auction_email(
        to_email=bid.bidder.email,
        subject=f'You have been outbid - {bid.auction.title}',
        template_name='outbid_notification',
        context=context
    )


def send_auction_ending_reminder(auction, participant):
    """Send auction ending soon reminder"""
    
    context = {
        'auction': auction,
        'user': participant.user,
        'time_remaining': calculate_time_remaining(auction)
    }
    
    send_auction_email(
        to_email=participant.user.email,
        subject=f'Auction Ending Soon - {auction.title}',
        template_name='auction_ending_reminder',
        context=context
    )


# ============================================================================
# REPORTING & EXPORT
# ============================================================================

def generate_auction_report(auction):
    """Generate comprehensive auction report data"""
    
    stats = get_auction_statistics(auction)
    
    report = {
        'auction': auction,
        'statistics': stats,
        'bids': auction.bids.select_related('bidder').order_by('-created_at'),
        'participants': auction.participants.filter(is_approved=True),
        'result': None,
        'financial_summary': {
            'starting_price': auction.starting_price,
            'reserve_price': auction.reserve_price,
            'final_price': auction.winning_bid_amount or Decimal('0.00'),
            'reserve_met': auction.reserve_met,
            'total_bid_value': stats['total_value']
        }
    }
    
    try:
        report['result'] = auction.result
    except:
        pass
    
    return report


def export_auction_bids_csv(auction):
    """Export auction bids to CSV format"""
    
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Bid Number',
        'Bidder',
        'Bid Amount',
        'Bid Type',
        'Timestamp',
        'Is Winning',
        'Is Outbid'
    ])
    
    # Data
    for idx, bid in enumerate(auction.bids.select_related('bidder').order_by('created_at'), 1):
        writer.writerow([
            idx,
            bid.bidder.get_full_name() or bid.bidder.username,
            f'${bid.bid_amount:,.2f}',
            bid.get_bid_type_display(),
            bid.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if bid.is_winning_bid else 'No',
            'Yes' if bid.is_outbid else 'No'
        ])
    
    return output.getvalue()


# ============================================================================
# SEARCH & FILTERING
# ============================================================================

def search_auctions(query, status=None, auction_type=None, price_min=None, price_max=None):
    """Search auctions with multiple filters"""
    
    queryset = Auction.objects.select_related('vehicle', 'created_by')
    
    # Text search
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(auction_number__icontains=query) |
            Q(vehicle__make__icontains=query) |
            Q(vehicle__model__icontains=query) |
            Q(vehicle__vin__icontains=query)
        )
    
    # Status filter
    if status:
        queryset = queryset.filter(status=status)
    
    # Auction type filter
    if auction_type:
        queryset = queryset.filter(auction_type=auction_type)
    
    # Price range filter
    if price_min:
        queryset = queryset.filter(starting_price__gte=price_min)
    
    if price_max:
        queryset = queryset.filter(starting_price__lte=price_max)
    
    return queryset


def get_featured_auctions(limit=10):
    """Get featured active auctions"""
    
    return Auction.objects.filter(
        status__in=['active', 'scheduled'],
        featured=True
    ).select_related('vehicle').order_by('-created_at')[:limit]


def get_ending_soon_auctions(hours=24, limit=10):
    """Get auctions ending within specified hours"""
    
    threshold = timezone.now() + timedelta(hours=hours)
    
    return Auction.objects.filter(
        status='active',
        end_date__lte=threshold,
        end_date__gt=timezone.now()
    ).select_related('vehicle').order_by('end_date')[:limit]


# ============================================================================
# AUCTION AUTOMATION
# ============================================================================

def auto_extend_auction(auction):
    """Automatically extend auction if bid placed near end"""
    
    if not auction.auto_extend:
        return False
    
    remaining = calculate_time_remaining(auction)
    if not remaining:
        return False
    
    # Check if within extension window (default 5 minutes)
    if remaining.total_seconds() < 300:
        auction.extended_end_date = auction.end_date + timedelta(minutes=auction.extension_minutes)
        auction.end_date = auction.extended_end_date
        auction.save(update_fields=['end_date', 'extended_end_date', 'updated_at'])
        return True
    
    return False


def process_proxy_bids(auction, new_bid_amount):
    """Process automatic proxy bids after a new bid"""
    
    # Get all active proxy bidders
    proxy_participants = auction.participants.filter(
        proxy_bid_enabled=True,
        proxy_max_amount__gt=new_bid_amount,
        is_approved=True
    ).exclude(user=auction.bids.order_by('-bid_amount').first().bidder)
    
    for participant in proxy_participants:
        # Calculate proxy bid
        proxy_amount = calculate_proxy_bid(
            auction,
            participant.proxy_max_amount,
            new_bid_amount
        )
        
        if proxy_amount and proxy_amount > new_bid_amount:
            # Place automatic proxy bid
            Bid.objects.create(
                auction=auction,
                bidder=participant.user,
                bid_amount=proxy_amount,
                bid_type='proxy',
                is_active=True
            )
            break  # Only one proxy bid at a time


# ============================================================================
# CLEANUP & MAINTENANCE
# ============================================================================

def cleanup_expired_auctions():
    """Clean up and finalize expired auctions"""
    
    expired = Auction.objects.filter(
        status='active',
        end_date__lt=timezone.now()
    )
    
    count = 0
    for auction in expired:
        auction.finalize_auction()
        count += 1
    
    return count


def archive_old_auctions(days=365):
    """Archive auctions older than specified days"""
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    old_auctions = Auction.objects.filter(
        status='completed',
        completed_at__lt=cutoff_date
    )
    
    # Could move to archive table or set archived flag
    # For now, just return count
    return old_auctions.count()