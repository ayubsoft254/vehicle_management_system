"""
Auctions App - Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count, Max, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from decimal import Decimal

from .models import (
    Auction, Bid, AuctionParticipant, 
    AuctionWatchlist, AuctionResult
)
from .forms import (
    AuctionForm, AuctionQuickCreateForm, AuctionSearchForm,
    BidForm, ProxyBidForm, BuyNowForm,
    AuctionParticipantForm, ParticipantApprovalForm,
    AuctionResultForm, AddToWatchlistForm
)
from apps.vehicles.models import Vehicle
from apps.notifications.models import Notification


# ============================================================================
# AUCTION LIST & SEARCH VIEWS
# ============================================================================

class AuctionListView(ListView):
    """Display list of auctions with filtering"""
    model = Auction
    template_name = 'auctions/auction_list.html'
    context_object_name = 'auctions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Auction.objects.select_related('vehicle', 'created_by').annotate(
            bid_count=Count('bids'),
            max_bid=Max('bids__bid_amount')
        )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Default to active and scheduled auctions
            queryset = queryset.filter(status__in=['active', 'scheduled'])
        
        # Filter by auction type
        auction_type = self.request.GET.get('auction_type')
        if auction_type:
            queryset = queryset.filter(auction_type=auction_type)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(auction_number__icontains=search) |
                Q(vehicle__make__icontains=search) |
                Q(vehicle__model__icontains=search) |
                Q(vehicle__vin__icontains=search)
            )
        
        # Price range
        min_price = self.request.GET.get('min_price')
        if min_price:
            queryset = queryset.filter(starting_price__gte=Decimal(min_price))
        
        max_price = self.request.GET.get('max_price')
        if max_price:
            queryset = queryset.filter(starting_price__lte=Decimal(max_price))
        
        # Featured only
        if self.request.GET.get('featured_only'):
            queryset = queryset.filter(featured=True)
        
        # Ordering
        order = self.request.GET.get('order', '-start_date')
        queryset = queryset.order_by(order)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AuctionSearchForm(self.request.GET)
        context['active_count'] = Auction.objects.filter(status='active').count()
        context['upcoming_count'] = Auction.objects.filter(status='scheduled').count()
        return context


def auction_search(request):
    """AJAX auction search"""
    query = request.GET.get('q', '')
    
    auctions = Auction.objects.filter(
        Q(title__icontains=query) |
        Q(auction_number__icontains=query) |
        Q(vehicle__make__icontains=query) |
        Q(vehicle__model__icontains=query),
        status__in=['active', 'scheduled']
    )[:10]
    
    results = [{
        'id': str(auction.id),
        'auction_number': auction.auction_number,
        'title': auction.title,
        'vehicle': str(auction.vehicle),
        'current_bid': float(auction.current_bid),
        'status': auction.status
    } for auction in auctions]
    
    return JsonResponse({'results': results})


# ============================================================================
# AUCTION DETAIL VIEW
# ============================================================================

class AuctionDetailView(DetailView):
    """Display auction details"""
    model = Auction
    template_name = 'auctions/auction_detail.html'
    context_object_name = 'auction'
    
    def get_object(self):
        obj = super().get_object()
        # Increment view count
        obj.views_count += 1
        obj.save(update_fields=['views_count'])
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        auction = self.object
        user = self.request.user
        
        # Recent bids
        context['recent_bids'] = auction.bids.select_related('bidder').order_by('-created_at')[:10]
        
        # Bid form
        if user.is_authenticated and auction.is_active:
            context['bid_form'] = BidForm(auction=auction, user=user)
        
        # Check if user is registered
        if user.is_authenticated:
            context['is_registered'] = AuctionParticipant.objects.filter(
                auction=auction, 
                user=user,
                is_approved=True
            ).exists()
            
            context['is_watching'] = AuctionWatchlist.objects.filter(
                auction=auction,
                user=user
            ).exists()
            
            context['user_bids'] = auction.bids.filter(bidder=user).order_by('-created_at')[:5]
            context['is_highest_bidder'] = auction.bids.filter(
                is_active=True
            ).order_by('-bid_amount').first()
            
            if context['is_highest_bidder']:
                context['is_highest_bidder'] = context['is_highest_bidder'].bidder == user
        
        # Statistics
        context['total_participants'] = auction.participants.filter(is_approved=True).count()
        context['average_bid'] = auction.bids.aggregate(avg=Avg('bid_amount'))['avg'] or 0
        
        return context


# ============================================================================
# AUCTION CRUD VIEWS
# ============================================================================

class AuctionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create new auction"""
    model = Auction
    form_class = AuctionForm
    template_name = 'auctions/auction_form.html'
    permission_required = 'auctions.add_auction'
    success_url = reverse_lazy('auctions:auction_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Auction {self.object.auction_number} created successfully.')
        return response


class AuctionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update existing auction"""
    model = Auction
    form_class = AuctionForm
    template_name = 'auctions/auction_form.html'
    permission_required = 'auctions.change_auction'
    
    def get_success_url(self):
        return reverse_lazy('auctions:auction_detail', kwargs={'pk': self.object.pk})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Auction updated successfully.')
        return response


class AuctionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete auction"""
    model = Auction
    template_name = 'auctions/auction_confirm_delete.html'
    permission_required = 'auctions.delete_auction'
    success_url = reverse_lazy('auctions:auction_list')
    
    def delete(self, request, *args, **kwargs):
        auction = self.get_object()
        
        # Prevent deletion of active auctions
        if auction.status == 'active':
            messages.error(request, 'Cannot delete active auction.')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        messages.success(request, f'Auction {auction.auction_number} deleted.')
        return super().delete(request, *args, **kwargs)


# ============================================================================
# BIDDING VIEWS
# ============================================================================

@login_required
@require_POST
def place_bid(request, pk):
    """Place a bid on an auction"""
    auction = get_object_or_404(Auction, pk=pk)
    
    if not auction.is_active:
        messages.error(request, 'This auction is not active.')
        return redirect('auctions:auction_detail', pk=pk)
    
    form = BidForm(request.POST, auction=auction, user=request.user)
    
    if form.is_valid():
        bid = form.save(commit=False)
        bid.ip_address = get_client_ip(request)
        bid.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        bid.save()
        
        messages.success(request, f'Bid of ${bid.bid_amount:,.2f} placed successfully!')
        
        # Check if auction should be extended
        time_remaining = auction.time_remaining
        if time_remaining and time_remaining.total_seconds() < 300:  # Less than 5 minutes
            auction.extend_auction()
            messages.info(request, 'Auction extended by 5 minutes due to late bid.')
        
        return redirect('auctions:auction_detail', pk=pk)
    else:
        for error in form.errors.values():
            messages.error(request, error[0])
        return redirect('auctions:auction_detail', pk=pk)


@login_required
@require_POST
def buy_now(request, pk):
    """Purchase auction at buy now price"""
    auction = get_object_or_404(Auction, pk=pk)
    
    if not auction.buy_now_price:
        messages.error(request, 'Buy now is not available for this auction.')
        return redirect('auctions:auction_detail', pk=pk)
    
    if not auction.is_active:
        messages.error(request, 'This auction is not active.')
        return redirect('auctions:auction_detail', pk=pk)
    
    form = BuyNowForm(request.POST, auction=auction)
    
    if form.is_valid():
        # Create winning bid
        bid = Bid.objects.create(
            auction=auction,
            bidder=request.user,
            bid_amount=auction.buy_now_price,
            bid_type='auto',
            is_winning_bid=True,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        # Finalize auction
        auction.winner = request.user
        auction.winning_bid_amount = auction.buy_now_price
        auction.status = 'completed'
        auction.completed_at = timezone.now()
        auction.save()
        
        messages.success(request, f'Congratulations! You purchased this vehicle for ${auction.buy_now_price:,.2f}')
        return redirect('auctions:auction_result', pk=pk)
    
    messages.error(request, 'Please confirm your purchase.')
    return redirect('auctions:auction_detail', pk=pk)


@login_required
def setup_proxy_bid(request, pk):
    """Setup proxy bidding for an auction"""
    auction = get_object_or_404(Auction, pk=pk)
    
    if not auction.allow_proxy_bidding:
        messages.error(request, 'Proxy bidding is not available for this auction.')
        return redirect('auctions:auction_detail', pk=pk)
    
    if request.method == 'POST':
        form = ProxyBidForm(request.POST, auction=auction)
        if form.is_valid():
            max_bid = form.cleaned_data['max_bid_amount']
            
            # Update or create participant with proxy settings
            participant, created = AuctionParticipant.objects.get_or_create(
                auction=auction,
                user=request.user,
                defaults={'is_approved': True}
            )
            
            participant.proxy_bid_enabled = True
            participant.proxy_max_amount = max_bid
            participant.save()
            
            messages.success(request, f'Proxy bidding set up with maximum bid of ${max_bid:,.2f}')
            return redirect('auctions:auction_detail', pk=pk)
    else:
        form = ProxyBidForm(auction=auction)
    
    return render(request, 'auctions/proxy_bid_form.html', {
        'form': form,
        'auction': auction
    })


@login_required
def my_bids(request):
    """View user's bidding history"""
    bids = Bid.objects.filter(bidder=request.user).select_related(
        'auction', 'auction__vehicle'
    ).order_by('-created_at')
    
    paginator = Paginator(bids, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bids': page_obj,
        'total_bids': bids.count(),
        'active_bids': bids.filter(auction__status='active').count(),
        'winning_bids': bids.filter(is_winning_bid=True).count()
    }
    
    return render(request, 'auctions/my_bids.html', context)


# ============================================================================
# PARTICIPATION VIEWS
# ============================================================================

@login_required
def register_for_auction(request, pk):
    """Register to participate in auction"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Check if already registered
    existing = AuctionParticipant.objects.filter(auction=auction, user=request.user).first()
    if existing:
        messages.info(request, 'You are already registered for this auction.')
        return redirect('auctions:auction_detail', pk=pk)
    
    if request.method == 'POST':
        form = AuctionParticipantForm(request.POST, auction=auction, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration submitted successfully. Awaiting approval.')
            return redirect('auctions:auction_detail', pk=pk)
    else:
        form = AuctionParticipantForm(auction=auction, user=request.user)
    
    return render(request, 'auctions/register_form.html', {
        'form': form,
        'auction': auction
    })


@login_required
@permission_required('auctions.change_auctionparticipant')
def approve_participant(request, pk):
    """Approve participant registration"""
    participant = get_object_or_404(AuctionParticipant, pk=pk)
    
    participant.approve(request.user)
    messages.success(request, f'{participant.user.get_full_name()} approved for auction.')
    
    return redirect('auctions:auction_detail', pk=participant.auction.pk)


@login_required
def my_auctions(request):
    """View user's auction participations"""
    participations = AuctionParticipant.objects.filter(
        user=request.user
    ).select_related('auction', 'auction__vehicle').order_by('-registered_at')
    
    context = {
        'participations': participations,
        'active_participations': participations.filter(auction__status='active').count(),
        'approved_count': participations.filter(is_approved=True).count()
    }
    
    return render(request, 'auctions/my_auctions.html', context)


# ============================================================================
# WATCHLIST VIEWS
# ============================================================================

@login_required
@require_POST
def add_to_watchlist(request, pk):
    """Add auction to watchlist"""
    auction = get_object_or_404(Auction, pk=pk)
    
    watchlist, created = AuctionWatchlist.objects.get_or_create(
        auction=auction,
        user=request.user,
        defaults={
            'notify_before_end': True,
            'notify_on_outbid': True
        }
    )
    
    if created:
        auction.watchers_count += 1
        auction.save(update_fields=['watchers_count'])
        messages.success(request, 'Auction added to watchlist.')
    else:
        messages.info(request, 'Auction already in watchlist.')
    
    return redirect('auctions:auction_detail', pk=pk)


@login_required
@require_POST
def remove_from_watchlist(request, pk):
    """Remove auction from watchlist"""
    auction = get_object_or_404(Auction, pk=pk)
    
    deleted_count = AuctionWatchlist.objects.filter(
        auction=auction,
        user=request.user
    ).delete()[0]
    
    if deleted_count:
        auction.watchers_count = max(0, auction.watchers_count - 1)
        auction.save(update_fields=['watchers_count'])
        messages.success(request, 'Auction removed from watchlist.')
    
    return redirect('auctions:auction_detail', pk=pk)


@login_required
def my_watchlist(request):
    """View user's watched auctions"""
    watchlist = AuctionWatchlist.objects.filter(
        user=request.user
    ).select_related('auction', 'auction__vehicle').order_by('-added_at')
    
    return render(request, 'auctions/my_watchlist.html', {
        'watchlist': watchlist
    })


# ============================================================================
# AUCTION RESULTS VIEWS
# ============================================================================

@login_required
def auction_result(request, pk):
    """View auction result"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Only winner, staff, or auction creator can view
    if not (request.user.is_staff or 
            auction.created_by == request.user or 
            auction.winner == request.user):
        return HttpResponseForbidden('You do not have permission to view this result.')
    
    try:
        result = auction.result
    except AuctionResult.DoesNotExist:
        result = None
    
    return render(request, 'auctions/auction_result.html', {
        'auction': auction,
        'result': result
    })


@login_required
@permission_required('auctions.change_auctionresult')
def update_auction_result(request, pk):
    """Update auction result"""
    result = get_object_or_404(AuctionResult, pk=pk)
    
    if request.method == 'POST':
        form = AuctionResultForm(request.POST, instance=result)
        if form.is_valid():
            form.save()
            messages.success(request, 'Auction result updated successfully.')
            return redirect('auctions:auction_result', pk=result.auction.pk)
    else:
        form = AuctionResultForm(instance=result)
    
    return render(request, 'auctions/result_form.html', {
        'form': form,
        'result': result
    })


# ============================================================================
# ADMIN ACTIONS
# ============================================================================

@login_required
@permission_required('auctions.change_auction')
def finalize_auction(request, pk):
    """Manually finalize an auction"""
    auction = get_object_or_404(Auction, pk=pk)
    
    if auction.status != 'active':
        messages.error(request, 'Only active auctions can be finalized.')
        return redirect('auctions:auction_detail', pk=pk)
    
    auction.finalize_auction()
    messages.success(request, 'Auction finalized successfully.')
    
    return redirect('auctions:auction_detail', pk=pk)


@login_required
@permission_required('auctions.change_auction')
def cancel_auction(request, pk):
    """Cancel an auction"""
    auction = get_object_or_404(Auction, pk=pk)
    
    if auction.status == 'completed':
        messages.error(request, 'Cannot cancel completed auction.')
        return redirect('auctions:auction_detail', pk=pk)
    
    auction.status = 'cancelled'
    auction.save()
    
    messages.success(request, 'Auction cancelled.')
    return redirect('auctions:auction_detail', pk=pk)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# DASHBOARD VIEWS
# ============================================================================

@login_required
def auction_dashboard(request):
    """Auction management dashboard"""
    context = {
        'active_auctions': Auction.objects.filter(status='active').count(),
        'scheduled_auctions': Auction.objects.filter(status='scheduled').count(),
        'completed_today': Auction.objects.filter(
            status='completed',
            completed_at__date=timezone.now().date()
        ).count(),
        'total_bids_today': Bid.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'my_active_bids': Bid.objects.filter(
            bidder=request.user,
            auction__status='active',
            is_active=True
        ).count(),
        'my_watchlist_count': AuctionWatchlist.objects.filter(user=request.user).count(),
        'recent_auctions': Auction.objects.select_related('vehicle').order_by('-created_at')[:5],
        'ending_soon': Auction.objects.filter(
            status='active',
            end_date__lte=timezone.now() + timezone.timedelta(hours=24)
        ).order_by('end_date')[:5]
    }
    
    return render(request, 'auctions/dashboard.html', context)


# ============================================================================
# API ENDPOINTS (JSON)
# ============================================================================

@login_required
def auction_status_api(request, pk):
    """Get current auction status (AJAX)"""
    auction = get_object_or_404(Auction, pk=pk)
    
    data = {
        'status': auction.status,
        'current_bid': float(auction.current_bid),
        'total_bids': auction.total_bids,
        'unique_bidders': auction.unique_bidders,
        'is_active': auction.is_active,
        'time_remaining': str(auction.time_remaining) if auction.time_remaining else None,
    }
    
    # Latest bid
    latest_bid = auction.bids.filter(is_active=True).order_by('-bid_amount').first()
    if latest_bid:
        data['highest_bidder'] = latest_bid.bidder.get_full_name() or latest_bid.bidder.username
        data['is_user_winning'] = latest_bid.bidder == request.user
    
    return JsonResponse(data)


@login_required
def recent_bids_api(request, pk):
    """Get recent bids for an auction (AJAX)"""
    auction = get_object_or_404(Auction, pk=pk)
    
    bids = auction.bids.select_related('bidder').order_by('-created_at')[:10]
    
    data = [{
        'bidder': bid.bidder.get_full_name() or bid.bidder.username,
        'amount': float(bid.bid_amount),
        'time': bid.created_at.isoformat(),
        'is_winning': bid.is_winning_bid
    } for bid in bids]
    
    return JsonResponse({'bids': data})