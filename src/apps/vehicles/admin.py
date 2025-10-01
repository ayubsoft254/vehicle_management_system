"""
Vehicles Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from .models import Vehicle, VehiclePhoto, VehicleHistory


class VehiclePhotoInline(admin.TabularInline):
    """Inline admin for vehicle photos"""
    model = VehiclePhoto
    extra = 1
    fields = ['image', 'caption', 'is_primary', 'order', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class VehicleHistoryInline(admin.TabularInline):
    """Inline admin for vehicle history"""
    model = VehicleHistory
    extra = 0
    fields = ['timestamp', 'changed_by', 'old_status', 'new_status', 'notes']
    readonly_fields = ['timestamp', 'changed_by', 'old_status', 'new_status']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    """Admin interface for Vehicles"""
    
    inlines = [VehiclePhotoInline, VehicleHistoryInline]
    
    list_display = [
        'vehicle_thumbnail', 'vehicle_info', 'year', 
        'status_badge', 'price_info', 'mileage_display',
        'is_active', 'is_featured', 'date_added'
    ]
    
    list_filter = [
        'status', 'is_active', 'is_featured', 'fuel_type', 
        'transmission', 'body_type', 'make', 'year', 'date_added'
    ]
    
    search_fields = [
        'make', 'model', 'vin', 'registration_number', 
        'color', 'description'
    ]
    
    list_editable = ['is_active', 'is_featured']
    
    readonly_fields = [
        'profit_display', 'profit_percentage_display',
        'date_added', 'last_updated', 'added_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                ('make', 'model', 'year'),
                ('vin', 'registration_number'),
                ('color', 'mileage'),
            )
        }),
        ('Specifications', {
            'fields': (
                ('fuel_type', 'transmission', 'engine_size'),
                ('body_type', 'seats', 'doors'),
                'condition',
            )
        }),
        ('Pricing', {
            'fields': (
                ('purchase_price', 'selling_price', 'deposit_required'),
                ('profit_display', 'profit_percentage_display'),
            ),
            'classes': ('wide',)
        }),
        ('Status & Flags', {
            'fields': (
                ('status', 'is_active', 'is_featured'),
            )
        }),
        ('Additional Information', {
            'fields': (
                'description',
                'features',
                'location',
            ),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': (
                ('purchase_date', 'date_sold'),
                ('date_added', 'last_updated'),
                'added_by',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'date_added'
    ordering = ['-date_added']
    list_per_page = 25
    
    actions = [
        'mark_as_available', 'mark_as_sold', 'mark_as_reserved',
        'activate_vehicles', 'deactivate_vehicles', 
        'mark_as_featured', 'remove_featured'
    ]
    
    def vehicle_thumbnail(self, obj):
        """Display vehicle thumbnail"""
        main_photo = obj.main_photo
        if main_photo and main_photo.image:
            return format_html(
                '<img src="{}" width="80" height="60" style="object-fit: cover; border-radius: 4px;" />',
                main_photo.image.url
            )
        return format_html('<div style="width: 80px; height: 60px; background-color: #e5e7eb; border-radius: 4px; display: flex; align-items: center; justify-content: center;"><i class="fas fa-car" style="color: #9ca3af;"></i></div>')
    vehicle_thumbnail.short_description = 'Photo'
    
    def vehicle_info(self, obj):
        """Display vehicle information"""
        return format_html(
            '<strong>{}</strong><br><small style="color: #6b7280;">{}</small><br><small style="color: #9ca3af;">VIN: {}</small>',
            obj.full_name,
            obj.registration_number or 'No registration',
            obj.vin[:10] + '...'
        )
    vehicle_info.short_description = 'Vehicle'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        color_map = {
            'available': '#10b981',
            'reserved': '#f59e0b',
            'sold': '#3b82f6',
            'repossessed': '#ef4444',
            'auctioned': '#8b5cf6',
            'maintenance': '#f97316',
        }
        color = color_map.get(obj.status, '#6b7280')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-block;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def price_info(self, obj):
        """Display pricing information"""
        profit_color = '#10b981' if obj.profit >= 0 else '#ef4444'
        return format_html(
            '<strong>KSh {:,}</strong><br>'
            '<small style="color: #6b7280;">Purchase: KSh {:,}</small><br>'
            '<small style="color: {};">Profit: KSh {:,}</small>',
            obj.selling_price,
            obj.purchase_price,
            profit_color,
            obj.profit
        )
    price_info.short_description = 'Price'
    
    def mileage_display(self, obj):
        """Display mileage formatted"""
        return format_html('{:,} KM', obj.mileage)
    mileage_display.short_description = 'Mileage'
    
    def profit_display(self, obj):
        """Display profit"""
        profit_color = 'green' if obj.profit >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KSh {:,}</span>',
            profit_color,
            obj.profit
        )
    profit_display.short_description = 'Profit'
    
    def profit_percentage_display(self, obj):
        """Display profit percentage"""
        percentage = obj.profit_percentage
        color = 'green' if percentage >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color,
            percentage
        )
    profit_percentage_display.short_description = 'Profit %'
    
    def save_model(self, request, obj, form, change):
        """Set added_by user on creation"""
        if not change:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)
    
    # Admin Actions
    
    def mark_as_available(self, request, queryset):
        """Mark selected vehicles as available"""
        count = 0
        for vehicle in queryset:
            vehicle.change_status('available', request.user, 'Marked as available via admin')
            count += 1
        self.message_user(request, f'{count} vehicle(s) marked as available.')
    mark_as_available.short_description = 'Mark as Available'
    
    def mark_as_sold(self, request, queryset):
        """Mark selected vehicles as sold"""
        count = 0
        for vehicle in queryset:
            vehicle.change_status('sold', request.user, 'Marked as sold via admin')
            count += 1
        self.message_user(request, f'{count} vehicle(s) marked as sold.')
    mark_as_sold.short_description = 'Mark as Sold'
    
    def mark_as_reserved(self, request, queryset):
        """Mark selected vehicles as reserved"""
        count = 0
        for vehicle in queryset:
            vehicle.change_status('reserved', request.user, 'Marked as reserved via admin')
            count += 1
        self.message_user(request, f'{count} vehicle(s) marked as reserved.')
    mark_as_reserved.short_description = 'Mark as Reserved'
    
    def activate_vehicles(self, request, queryset):
        """Activate selected vehicles"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} vehicle(s) activated.')
    activate_vehicles.short_description = 'Activate selected vehicles'
    
    def deactivate_vehicles(self, request, queryset):
        """Deactivate selected vehicles"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} vehicle(s) deactivated.')
    deactivate_vehicles.short_description = 'Deactivate selected vehicles'
    
    def mark_as_featured(self, request, queryset):
        """Mark selected vehicles as featured"""
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} vehicle(s) marked as featured.')
    mark_as_featured.short_description = 'Mark as Featured'
    
    def remove_featured(self, request, queryset):
        """Remove featured flag from selected vehicles"""
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} vehicle(s) removed from featured.')
    remove_featured.short_description = 'Remove Featured'
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist"""
        extra_context = extra_context or {}
        
        # Get statistics
        total_vehicles = Vehicle.objects.count()
        available = Vehicle.objects.filter(status='available').count()
        sold = Vehicle.objects.filter(status='sold').count()
        
        total_value = Vehicle.objects.filter(
            status='available'
        ).aggregate(total=Sum('selling_price'))['total'] or 0
        
        extra_context['total_vehicles'] = total_vehicles
        extra_context['available'] = available
        extra_context['sold'] = sold
        extra_context['total_value'] = total_value
        
        return super().changelist_view(request, extra_context)


@admin.register(VehiclePhoto)
class VehiclePhotoAdmin(admin.ModelAdmin):
    """Admin interface for Vehicle Photos"""
    
    list_display = ['photo_thumbnail', 'vehicle', 'caption', 'is_primary', 'order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['vehicle__make', 'vehicle__model', 'caption']
    list_editable = ['is_primary', 'order']
    readonly_fields = ['uploaded_at', 'uploaded_by']
    
    def photo_thumbnail(self, obj):
        """Display photo thumbnail"""
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="75" style="object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return '-'
    photo_thumbnail.short_description = 'Thumbnail'


@admin.register(VehicleHistory)
class VehicleHistoryAdmin(admin.ModelAdmin):
    """Admin interface for Vehicle History"""
    
    list_display = ['vehicle', 'timestamp', 'changed_by', 'status_change', 'notes_short']
    list_filter = ['old_status', 'new_status', 'timestamp']
    search_fields = ['vehicle__make', 'vehicle__model', 'notes']
    readonly_fields = ['vehicle', 'changed_by', 'old_status', 'new_status', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def status_change(self, obj):
        """Display status change"""
        return format_html(
            '{} <span style="color: #9ca3af;">→</span> {}',
            obj.old_status.upper(),
            obj.new_status.upper()
        )
    status_change.short_description = 'Status Change'
    
    def notes_short(self, obj):
        """Display shortened notes"""
        if obj.notes:
            return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
        return '-'
    notes_short.short_description = 'Notes'
    
    def has_add_permission(self, request):
        """Don't allow manual creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete history"""
        return request.user.is_superuser