
from django.contrib import admin
from .models import Auction, AuctionVehicle

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
	list_display = ("title", "location", "start_date", "end_date", "status", "created_by")
	search_fields = ("title", "location")
	list_filter = ("status", "start_date")

@admin.register(AuctionVehicle)
class AuctionVehicleAdmin(admin.ModelAdmin):
	list_display = ("auction", "vehicle", "lot_number", "status", "final_bid")
	search_fields = ("lot_number", "vehicle__vin")
	list_filter = ("status", "auction")
