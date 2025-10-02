"""
Auctions App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    # Auction List & Search
    path('', views.AuctionListView.as_view(), name='auction_list'),
    path('search/', views.auction_search, name='auction_search'),
    path('dashboard/', views.auction_dashboard, name='dashboard'),
    
    # Auction CRUD
    path('create/', views.AuctionCreateView.as_view(), name='auction_create'),
    path('<uuid:pk>/', views.AuctionDetailView.as_view(), name='auction_detail'),
    path('<uuid:pk>/edit/', views.AuctionUpdateView.as_view(), name='auction_edit'),
    path('<uuid:pk>/delete/', views.AuctionDeleteView.as_view(), name='auction_delete'),
    
    # Bidding
    path('<uuid:pk>/bid/', views.place_bid, name='place_bid'),
    path('<uuid:pk>/buy-now/', views.buy_now, name='buy_now'),
    path('<uuid:pk>/proxy-bid/', views.setup_proxy_bid, name='setup_proxy_bid'),
    path('my-bids/', views.my_bids, name='my_bids'),
    
    # Participation
    path('<uuid:pk>/register/', views.register_for_auction, name='register'),
    path('participant/<uuid:pk>/approve/', views.approve_participant, name='approve_participant'),
    path('my-auctions/', views.my_auctions, name='my_auctions'),
    
    # Watchlist
    path('<uuid:pk>/watch/', views.add_to_watchlist, name='add_to_watchlist'),
    path('<uuid:pk>/unwatch/', views.remove_from_watchlist, name='remove_from_watchlist'),
    path('watchlist/', views.my_watchlist, name='my_watchlist'),
    
    # Results
    path('<uuid:pk>/result/', views.auction_result, name='auction_result'),
    path('result/<uuid:pk>/update/', views.update_auction_result, name='update_result'),
    
    # Admin Actions
    path('<uuid:pk>/finalize/', views.finalize_auction, name='finalize_auction'),
    path('<uuid:pk>/cancel/', views.cancel_auction, name='cancel_auction'),
    
    # API Endpoints
    path('api/<uuid:pk>/status/', views.auction_status_api, name='auction_status_api'),
    path('api/<uuid:pk>/recent-bids/', views.recent_bids_api, name='recent_bids_api'),
]