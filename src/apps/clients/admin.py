"""
Admin configuration for client app
Provides admin interface for managing clients, vehicles, payments, and documents
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Client, ClientVehicle, ClientDocument
from apps.payments.models import Payment


# ==================== INLINE ADMINS ====================

class ClientVehicleInline(admin.TabularInline):
    """
    Inline admin for client vehicles
    """
    model = ClientVehicle
    extra = 0
    fields = [
        'vehicle', 'purchase_date', 'purchase_price', 
        'deposit_paid', 'balance', 'is_paid_off'
    ]
    readonly_fields = ['balance', 'is_paid_off']
    can_delete = False


class ClientDocumentInline(admin.TabularInline):
    """
    Inline admin for client documents
    """
    model = ClientDocument
    extra = 0
    fields = ['document_type', 'title', 'file', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class PaymentInline(admin.TabularInline):
    """
    Inline admin for payments
    """
    model = Payment
    extra = 0
    fields = ['payment_date', 'amount', 'payment_method', 'transaction_reference', 'recorded_by']
    readonly_fields = ['recorded_by']
    can_delete = False


# ==================== CLIENT ADMIN ====================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin interface for Client model
    """
    list_display = [
        'id', 'get_full_name_display', 'id_number', 'phone_primary',
        'status_badge', 'credit_limit_display', 'available_credit_display',
        'total_purchases_display', 'date_registered'
    ]
    
    list_filter = [
        'status', 'id_type', 'gender', 'is_active',
        'date_registered', 'city', 'county'
    ]
    
    search_fields = [
        'first_name', 'other_names', 'last_name',
        'id_number', 'phone_primary', 'phone_secondary',
        'email'
    ]
    
    readonly_fields = [
        'date_registered', 'last_updated', 'registered_by',
        'available_credit_display', 'credit_utilization_display',
        'total_purchases_display', 'total_spent_display',
        'total_paid_display', 'total_balance_display',
        'profile_photo_preview'
    ]
    
    fieldsets = (
        ('Personal Information', {
            'fields': (
                'profile_photo',
                'profile_photo_preview',
                ('first_name', 'other_names', 'last_name'),
                ('id_type', 'id_number'),
                ('date_of_birth', 'gender'),
            )
        }),
        ('Contact Information', {
            'fields': (
                ('phone_primary', 'phone_secondary'),
                'email',
                'physical_address',
                ('city', 'county'),
                'postal_address',
            )
        }),
        ('Employment Information', {
            'fields': (
                'occupation',
                'employer',
                'monthly_income',
            ),
            'classes': ('collapse',)
        }),
        ('Next of Kin', {
            'fields': (
                'next_of_kin_name',
                'next_of_kin_phone',
                'next_of_kin_relationship',
                'next_of_kin_address',
            ),
            'classes': ('collapse',)
        }),
        ('Financial Information', {
            'fields': (
                ('credit_limit', 'available_credit_display'),
                'credit_utilization_display',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_purchases_display',
                'total_spent_display',
                'total_paid_display',
                'total_balance_display',
            ),
            'classes': ('collapse',)
        }),
        ('Status & Settings', {
            'fields': (
                ('status', 'is_active'),
                'notes',
            )
        }),
        ('System Information', {
            'fields': (
                'registered_by',
                ('date_registered', 'last_updated'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ClientVehicleInline, ClientDocumentInline]
    
    list_per_page = 25
    date_hierarchy = 'date_registered'
    
    actions = ['activate_clients', 'deactivate_clients', 'mark_as_defaulted']
    
    def profile_photo_preview(self, obj):
        """Display profile photo preview"""
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; '
                'border-radius: 8px; border: 2px solid #ddd;" />',
                obj.profile_photo.url
            )
        return format_html(
            '<div style="width: 150px; height: 150px; background-color: #f0f0f0; '
            'border-radius: 8px; display: flex; align-items: center; justify-content: center; '
            'border: 2px solid #ddd;">'
            '<span style="color: #999; font-size: 14px;">No Photo</span></div>'
        )
    profile_photo_preview.short_description = 'Current Photo'
    
    def get_full_name_display(self, obj):
        """Display full name with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:clients_client_change', args=[obj.pk]),
            obj.get_full_name()
        )
    get_full_name_display.short_description = 'Full Name'
    get_full_name_display.admin_order_field = 'first_name'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'defaulted': '#dc3545',
            'completed': '#007bff',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def credit_limit_display(self, obj):
        """Display credit limit formatted"""
        return format_html('KES {}', f'{obj.credit_limit:,.2f}')
    credit_limit_display.short_description = 'Credit Limit'
    credit_limit_display.admin_order_field = 'credit_limit'
    
    def available_credit_display(self, obj):
        """Display available credit formatted"""
        return format_html('KES {}', f'{obj.available_credit:,.2f}')
    available_credit_display.short_description = 'Available Credit'
    
    def credit_utilization_display(self, obj):
        """Display credit utilization as percentage"""
        utilization = obj.credit_utilization
        color = '#dc3545' if utilization > 80 else '#28a745' if utilization < 50 else '#ffc107'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            f'{utilization:.1f}%'
        )
    credit_utilization_display.short_description = 'Credit Utilization'
    
    def total_purchases_display(self, obj):
        """Display total number of purchases"""
        count = obj.vehicles.count()
        return format_html('<strong>{}</strong>', count)
    total_purchases_display.short_description = 'Total Purchases'
    
    def total_spent_display(self, obj):
        """Display total amount spent"""
        total = obj.vehicles.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        return format_html('KES {}', f'{total:,.2f}')
    total_spent_display.short_description = 'Total Spent'
    
    def total_paid_display(self, obj):
        """Display total amount paid"""
        total = obj.vehicles.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
        return format_html('KES {}', f'{total:,.2f}')
    total_paid_display.short_description = 'Total Paid'
    
    def total_balance_display(self, obj):
        """Display total balance"""
        total = obj.vehicles.aggregate(Sum('balance'))['balance__sum'] or 0
        color = '#dc3545' if total > 0 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KES {}</span>',
            color,
            f'{total:,.2f}'
        )
    total_balance_display.short_description = 'Total Balance'
    
    def activate_clients(self, request, queryset):
        """Bulk action to activate clients"""
        updated = queryset.update(status='active', is_active=True)
        self.message_user(request, f'{updated} client(s) activated successfully.')
    activate_clients.short_description = 'Activate selected clients'
    
    def deactivate_clients(self, request, queryset):
        """Bulk action to deactivate clients"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} client(s) deactivated successfully.')
    deactivate_clients.short_description = 'Deactivate selected clients'
    
    def mark_as_defaulted(self, request, queryset):
        """Bulk action to mark clients as defaulted"""
        updated = queryset.update(status='defaulted')
        self.message_user(request, f'{updated} client(s) marked as defaulted.')
    mark_as_defaulted.short_description = 'Mark as defaulted'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.registered_by = request.user
        super().save_model(request, obj, form, change)


# ==================== CLIENT VEHICLE ADMIN ====================

@admin.register(ClientVehicle)
class ClientVehicleAdmin(admin.ModelAdmin):
    """
    Admin interface for ClientVehicle model
    """
    list_display = [
        'id', 'client_link', 'vehicle_link', 'purchase_date',
        'purchase_price_display', 'total_paid_display',
        'balance_display', 'payment_progress_display', 'paid_off_badge'
    ]
    
    list_filter = [
        'is_paid_off', 'purchase_date', 'created_at'
    ]
    
    search_fields = [
        'client__first_name', 'client__last_name', 'client__id_number',
        'vehicle__make', 'vehicle__model', 'vehicle__registration_number',
        'contract_number'
    ]
    
    readonly_fields = [
        'balance', 'total_paid', 'is_paid_off', 'created_at', 'updated_at', 'created_by',
        'payment_progress_display'
    ]
    
    fieldsets = (
        ('Vehicle Assignment', {
            'fields': (
                ('client', 'vehicle'),
                'purchase_date',
                'contract_number',
            )
        }),
        ('Financial Details', {
            'fields': (
                'purchase_price',
                ('deposit_paid', 'total_paid'),
                'balance',
                ('monthly_installment', 'installment_months'),
                'interest_rate',
                'payment_progress_display',
                'is_paid_off',
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            )
        }),
        ('System Information', {
            'fields': (
                'created_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PaymentInline]
    
    list_per_page = 25
    date_hierarchy = 'purchase_date'
    
    def client_link(self, obj):
        """Display client name with link"""
        url = reverse('admin:clients_client_change', args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client__first_name'
    
    def vehicle_link(self, obj):
        """Display vehicle with link"""
        url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.pk])
        return format_html('<a href="{}">{}</a>', url, obj.vehicle)
    vehicle_link.short_description = 'Vehicle'
    vehicle_link.admin_order_field = 'vehicle__make'
    
    def purchase_price_display(self, obj):
        """Display purchase price formatted"""
        return format_html('KES {}', f'{obj.purchase_price:,.2f}')
    purchase_price_display.short_description = 'Purchase Price'
    purchase_price_display.admin_order_field = 'purchase_price'
    
    def total_paid_display(self, obj):
        """Display total paid formatted"""
        return format_html('KES {}', f'{obj.total_paid:,.2f}')
    total_paid_display.short_description = 'Total Paid'
    total_paid_display.admin_order_field = 'total_paid'
    
    def balance_display(self, obj):
        """Display balance formatted"""
        color = '#dc3545' if obj.balance > 0 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KES {}</span>',
            color,
            f'{obj.balance:,.2f}'
        )
    balance_display.short_description = 'Balance'
    balance_display.admin_order_field = 'balance'
    
    def payment_progress_display(self, obj):
        """Display payment progress as progress bar"""
        progress = obj.payment_progress
        color = '#28a745' if progress > 75 else '#ffc107' if progress > 50 else '#dc3545'
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'text-align: center; border-radius: 3px; padding: 2px 0; font-size: 11px;">'
            '{}</div></div>',
            progress, color, f'{progress:.1f}%'
        )
    payment_progress_display.short_description = 'Progress'
    
    def paid_off_badge(self, obj):
        """Display paid off status as badge"""
        if obj.is_paid_off:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">PAID OFF</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">PENDING</span>'
        )
    paid_off_badge.short_description = 'Status'
    paid_off_badge.admin_order_field = 'is_paid_off'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== CLIENT DOCUMENT ADMIN ====================

@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for ClientDocument model
    """
    list_display = [
        'id', 'client_link', 'document_type_badge', 'title',
        'file_size_display', 'file_extension_display',
        'uploaded_by', 'uploaded_at'
    ]
    
    list_filter = [
        'document_type', 'uploaded_at'
    ]
    
    search_fields = [
        'client__first_name', 'client__last_name',
        'title', 'description'
    ]
    
    readonly_fields = [
        'uploaded_by', 'uploaded_at', 'file_size_display', 'file_extension_display'
    ]
    
    fieldsets = (
        ('Document Information', {
            'fields': (
                'client',
                ('document_type', 'title'),
                'file',
                'description',
            )
        }),
        ('File Information', {
            'fields': (
                'file_size_display',
                'file_extension_display',
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'uploaded_by',
                'uploaded_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 25
    date_hierarchy = 'uploaded_at'
    
    def client_link(self, obj):
        """Display client name with link"""
        url = reverse('admin:clients_client_change', args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client__first_name'
    
    def document_type_badge(self, obj):
        """Display document type as badge"""
        colors = {
            'id_card': '#007bff',
            'passport': '#17a2b8',
            'contract': '#28a745',
            'agreement': '#ffc107',
            'logbook': '#dc3545',
            'insurance': '#6f42c1',
            'other': '#6c757d',
        }
        color = colors.get(obj.document_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_document_type_display().upper()
        )
    document_type_badge.short_description = 'Type'
    document_type_badge.admin_order_field = 'document_type'
    
    def file_size_display(self, obj):
        """Display file size"""
        return obj.file_size
    file_size_display.short_description = 'File Size'
    
    def file_extension_display(self, obj):
        """Display file extension"""
        return obj.file_extension
    file_extension_display.short_description = 'File Type'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)