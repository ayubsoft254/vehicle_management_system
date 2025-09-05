from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from .models import Auction, AuctionVehicle


class AuctionListView(ListView):
	model = Auction
	template_name = 'auctions/auction_list.html'
	context_object_name = 'auctions'


class AuctionDetailView(DetailView):
	model = Auction
	template_name = 'auctions/auction_detail.html'
	context_object_name = 'auction'


class AuctionCreateView(CreateView):
	model = Auction
	fields = ['title', 'description', 'location', 'start_date', 'end_date', 'registration_deadline', 'registration_fee', 'status']
	template_name = 'auctions/auction_form.html'
	success_url = reverse_lazy('auctions:auction-list')

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		return super().form_valid(form)


class AuctionVehicleListView(ListView):
	model = AuctionVehicle
	template_name = 'auctions/auctionvehicle_list.html'
	context_object_name = 'auction_vehicles'

	def get_queryset(self):
		auction_id = self.kwargs.get('auction_id')
		return AuctionVehicle.objects.filter(auction_id=auction_id)


class AuctionVehicleDetailView(DetailView):
	model = AuctionVehicle
	template_name = 'auctions/auctionvehicle_detail.html'
	context_object_name = 'auction_vehicle'


class AuctionVehicleCreateView(CreateView):
	model = AuctionVehicle
	fields = ['auction', 'vehicle', 'lot_number', 'reserve_price', 'starting_bid', 'valuation_fee', 'advertisement_fee', 'parking_fee', 'other_expenses', 'status', 'notes']
	template_name = 'auctions/auctionvehicle_form.html'
	success_url = reverse_lazy('auctions:auction-list')

	def form_valid(self, form):
		form.instance.added_by = self.request.user
		return super().form_valid(form)
