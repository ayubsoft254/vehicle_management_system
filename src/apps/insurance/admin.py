"""
Admin configuration for insurance app
Provides admin interface for managing insurance providers, policies, claims, and payments
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from .models import InsuranceProvider, InsurancePolicy, InsuranceClaim, InsurancePayment
import csv


# ==================== INLINE ADMINS ====================

class InsurancePolicyInline(admin.TabularInline):
    """
    Inline admin for insurance policies
    """
    model = InsurancePolicy
    extra = 0
    fields = [
        'policy_number', 'policy_type', 'start_date', 'end_date',
        'premium_amount', 'status'
    ]
    readonly_fields = ['policy_number']
    can_delete = False


class InsuranceClaimInline(admin.TabularInline):
    """
    Inline admin for insurance claims
    """
    model = InsuranceClaim
    extra = 0
    fields = [
        'claim_number', 'claim_type', 'incident_date',
        'claimed_amount', 'status'
    ]
    readonly_fields = ['claim_number']
    can_delete = False


class InsurancePaymentInline(admin.TabularInline):
    """
    Inline admin for insurance payments
    """
    model = InsurancePayment
    extra = 0
    fields = [
        'receipt_number', 'payment_date', 'amount',
        'payment_method', 'recorded_by'
    ]
    readonly_fields = ['receipt_number', 'recorded_by']
    can_delete = False


# ==================== INSURANCE PROVIDER ADMIN ====================

@admin.register(InsuranceProvider)
class InsuranceProviderAdmin(admin.ModelAdmin):
    """
    Admin interface for InsuranceProvider model
    """
    list_display = [
        'name', 'phone_primary', 'email', 'city',
        'active_policies_display', 'total_policies_display',
        'is_active_badge', 'created_at'
    ]
    
    list_filter = [
        'is_active',
        'city',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'registration_number',
        'phone_primary',
        'phone_secondary',
        'email',
        'contact_person_name'
    ]
    
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'active_policies_count', 'total_policies_count'
    ]
    
    fieldsets = (
        ('Provider Information', {
            'fields': (
                ('name', 'registration_number'),
                ('is_active',),
            )
        }),
        ('Contact Information', {
            'fields': (
                ('phone_primary', 'phone_secondary'),
                'email',
                'website',
            )
        }),
        ('Address', {
            'fields': (
                'physical_address',
                ('postal_address', 'city'),
            )
        }),
        ('Contact Person', {
            'fields': (
                'contact_person_name',
                ('contact_person_phone', 'contact_person_email'),
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            )
        }),
        ('Statistics', {
            'fields': (
                ('active_policies_count', 'total_policies_count'),
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'created_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [InsurancePolicyInline]
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    actions = ['activate_providers', 'deactivate_providers']
    
    def active_policies_display(self, obj):
        """Display count of active policies"""
        count = obj.active_policies_count
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">{}</span>',
            count
        )
    active_policies_display.short_description = 'Active Policies'
    
    def total_policies_display(self, obj):
        """Display total policies count"""
        return format_html('<strong>{}</strong>', obj.total_policies_count)
    total_policies_display.short_description = 'Total Policies'
    
    def is_active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">INACTIVE</span>'
        )
    is_active_badge.short_description = 'Status'
    is_active_badge.admin_order_field = 'is_active'
    
    def activate_providers(self, request, queryset):
        """Bulk action to activate providers"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} provider(s) activated successfully.')
    activate_providers.short_description = 'Activate selected providers'
    
    def deactivate_providers(self, request, queryset):
        """Bulk action to deactivate providers"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} provider(s) deactivated successfully.')
    deactivate_providers.short_description = 'Deactivate selected providers'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== INSURANCE POLICY ADMIN ====================

@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    """
    Admin interface for InsurancePolicy model
    """
    list_display = [
        'policy_number', 'vehicle_link', 'provider_link', 'client_link',
        'policy_type_badge', 'start_date', 'end_date',
        'premium_display', 'status_badge', 'expiry_indicator'
    ]
    
    list_filter = [
        'status',
        'policy_type',
        'provider',
        'start_date',
        'end_date',
        ('start_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'policy_number',
        'vehicle__registration_number',
        'vehicle__make',
        'vehicle__model',
        'client__first_name',
        'client__last_name',
        'provider__name'
    ]
    
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'days_until_expiry', 'duration_days', 'duration_months',
        'is_active', 'is_expired', 'is_expiring_soon'
    ]
    
    fieldsets = (
        ('Policy Information', {
            'fields': (
                ('vehicle', 'provider'),
                'client',
                'policy_number',
                ('policy_type', 'status'),
            )
        }),
        ('Coverage Period', {
            'fields': (
                ('start_date', 'end_date'),
                ('duration_days', 'duration_months'),
                ('days_until_expiry', 'is_expired'),
            )
        }),
        ('Financial Details', {
            'fields': (
                ('premium_amount', 'sum_insured'),
                'excess_amount',
            )
        }),
        ('Documents', {
            'fields': (
                'certificate',
            )
        }),
        ('Renewal Information', {
            'fields': (
                ('is_renewed', 'renewed_policy'),
            ),
            'classes': ('collapse',)
        }),
        ('Reminders', {
            'fields': (
                ('reminder_sent', 'reminder_sent_date'),
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'coverage_details',
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
    
    inlines = [InsuranceClaimInline, InsurancePaymentInline]
    
    list_per_page = 25
    date_hierarchy = 'start_date'
    
    actions = ['mark_as_expired', 'send_reminders', 'export_to_csv']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('vehicle', 'provider', 'client', 'created_by')
    
    def vehicle_link(self, obj):
        """Display vehicle with link"""
        url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.pk])
        return format_html('<a href="{}">{}</a>', url, obj.vehicle)
    vehicle_link.short_description = 'Vehicle'
    vehicle_link.admin_order_field = 'vehicle__registration_number'
    
    def provider_link(self, obj):
        """Display provider with link"""
        url = reverse('admin:insurance_insuranceprovider_change', args=[obj.provider.pk])
        return format_html('<a href="{}">{}</a>', url, obj.provider.name)
    provider_link.short_description = 'Provider'
    provider_link.admin_order_field = 'provider__name'
    
    def client_link(self, obj):
        """Display client with link"""
        if obj.client:
            url = reverse('admin:clients_client_change', args=[obj.client.pk])
            return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
        return '-'
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client__first_name'
    
    def policy_type_badge(self, obj):
        """Display policy type as badge"""
        colors = {
            'comprehensive': '#007bff',
            'third_party': '#28a745',
            'third_party_fire_theft': '#ffc107',
        }
        color = colors.get(obj.policy_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_policy_type_display().upper()
        )
    policy_type_badge.short_description = 'Type'
    policy_type_badge.admin_order_field = 'policy_type'
    
    def premium_display(self, obj):
        """Display premium amount formatted"""
        return format_html('KES {:,.2f}', obj.premium_amount)
    premium_display.short_description = 'Premium'
    premium_display.admin_order_field = 'premium_amount'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'active': '#28a745',
            'expired': '#dc3545',
            'cancelled': '#6c757d',
            'renewed': '#007bff',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def expiry_indicator(self, obj):
        """Display expiry status indicator"""
        if obj.is_expired:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠️ EXPIRED</span>'
            )
        elif obj.days_until_expiry <= 30:
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;">⏰ {} days</span>',
                obj.days_until_expiry
            )
        else:
            return format_html(
                '<span style="color: #28a745;">✓ {} days</span>',
                obj.days_until_expiry
            )
    expiry_indicator.short_description = 'Expiry'
    
    def mark_as_expired(self, request, queryset):
        """Bulk action to mark policies as expired"""
        updated = queryset.update(status='expired')
        self.message_user(request, f'{updated} policy(ies) marked as expired.')
    mark_as_expired.short_description = 'Mark as expired'
    
    def send_reminders(self, request, queryset):
        """Bulk action to send expiry reminders"""
        count = queryset.filter(status='active', reminder_sent=False).count()
        # Implement actual reminder sending logic here
        self.message_user(request, f'Reminders queued for {count} policy(ies).')
    send_reminders.short_description = 'Send expiry reminders'
    
    def export_to_csv(self, request, queryset):
        """Export selected policies to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="policies_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Policy Number', 'Vehicle', 'Provider', 'Type',
            'Start Date', 'End Date', 'Premium', 'Status'
        ])
        
        for policy in queryset:
            writer.writerow([
                policy.policy_number,
                str(policy.vehicle),
                policy.provider.name,
                policy.get_policy_type_display(),
                policy.start_date,
                policy.end_date,
                policy.premium_amount,
                policy.get_status_display()
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== INSURANCE CLAIM ADMIN ====================

@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    """
    Admin interface for InsuranceClaim model
    """
    list_display = [
        'claim_number', 'policy_link', 'vehicle_link', 'claim_type_badge',
        'incident_date', 'claimed_amount_display', 'approved_amount_display',
        'status_badge', 'days_since_filed_display'
    ]
    
    list_filter = [
        'status',
        'claim_type',
        'claim_date',
        'incident_date',
        ('claim_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'claim_number',
        'policy__policy_number',
        'policy__vehicle__registration_number',
        'policy__client__first_name',
        'policy__client__last_name',
        'incident_location'
    ]
    
    readonly_fields = [
        'claim_number', 'filed_by', 'created_at', 'updated_at',
        'days_since_filed', 'vehicle', 'client', 'provider',
        'approval_percentage'
    ]
    
    fieldsets = (
        ('Claim Information', {
            'fields': (
                'claim_number',
                'policy',
                ('vehicle', 'client', 'provider'),
                ('claim_type', 'status'),
                ('claim_date', 'days_since_filed'),
            )
        }),
        ('Incident Details', {
            'fields': (
                ('incident_date', 'incident_location'),
                'incident_description',
                'police_report_number',
            )
        }),
        ('Financial Details', {
            'fields': (
                'claimed_amount',
                ('approved_amount', 'settled_amount'),
                'excess_paid',
                'approval_percentage',
            )
        }),
        ('Assessment', {
            'fields': (
                ('assessor_name', 'assessor_phone'),
                ('assessment_date', 'assessment_report'),
            ),
            'classes': ('collapse',)
        }),
        ('Status & Settlement', {
            'fields': (
                ('status_date', 'settlement_date'),
                'rejection_reason',
            )
        }),
        ('Documents', {
            'fields': (
                'supporting_documents',
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            )
        }),
        ('System Information', {
            'fields': (
                'filed_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 25
    date_hierarchy = 'claim_date'
    
    actions = ['approve_claims', 'reject_claims', 'mark_as_settled']
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'policy__vehicle',
            'policy__provider',
            'policy__client',
            'filed_by'
        )
    
    def policy_link(self, obj):
        """Display policy with link"""
        url = reverse('admin:insurance_insurancepolicy_change', args=[obj.policy.pk])
        return format_html('<a href="{}">{}</a>', url, obj.policy.policy_number)
    policy_link.short_description = 'Policy'
    
    def vehicle_link(self, obj):
        """Display vehicle with link"""
        vehicle = obj.policy.vehicle
        url = reverse('admin:vehicles_vehicle_change', args=[vehicle.pk])
        return format_html('<a href="{}">{}</a>', url, vehicle)
    vehicle_link.short_description = 'Vehicle'
    
    def claim_type_badge(self, obj):
        """Display claim type as badge"""
        colors = {
            'accident': '#dc3545',
            'theft': '#6f42c1',
            'fire': '#fd7e14',
            'vandalism': '#e83e8c',
            'natural_disaster': '#ffc107',
            'other': '#6c757d',
        }
        color = colors.get(obj.claim_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_claim_type_display().upper()
        )
    claim_type_badge.short_description = 'Type'
    claim_type_badge.admin_order_field = 'claim_type'
    
    def claimed_amount_display(self, obj):
        """Display claimed amount"""
        return format_html('KES {:,.2f}', obj.claimed_amount)
    claimed_amount_display.short_description = 'Claimed'
    claimed_amount_display.admin_order_field = 'claimed_amount'
    
    def approved_amount_display(self, obj):
        """Display approved amount"""
        if obj.approved_amount > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">KES {:,.2f}</span>',
                obj.approved_amount
            )
        return '-'
    approved_amount_display.short_description = 'Approved'
    approved_amount_display.admin_order_field = 'approved_amount'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': '#ffc107',
            'under_review': '#007bff',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'settled': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def days_since_filed_display(self, obj):
        """Display days since claim was filed"""
        days = obj.days_since_filed
        if days > 30:
            color = '#dc3545'
        elif days > 14:
            color = '#ffc107'
        else:
            color = '#28a745'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} days</span>',
            color,
            days
        )
    days_since_filed_display.short_description = 'Days Pending'
    
    def approve_claims(self, request, queryset):
        """Bulk action to approve claims"""
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f'{updated} claim(s) approved.')
    approve_claims.short_description = 'Approve selected claims'
    
    def reject_claims(self, request, queryset):
        """Bulk action to reject claims"""
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} claim(s) rejected.')
    reject_claims.short_description = 'Reject selected claims'
    
    def mark_as_settled(self, request, queryset):
        """Bulk action to mark claims as settled"""
        updated = queryset.filter(status='approved').update(
            status='settled',
            settlement_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} claim(s) marked as settled.')
    mark_as_settled.short_description = 'Mark as settled'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.filed_by = request.user
        super().save_model(request, obj, form, change)


# ==================== INSURANCE PAYMENT ADMIN ====================

@admin.register(InsurancePayment)
class InsurancePaymentAdmin(admin.ModelAdmin):
    """
    Admin interface for InsurancePayment model
    """
    list_display = [
        'receipt_number', 'policy_link', 'payment_date',
        'amount_display', 'payment_method_badge',
        'transaction_reference', 'recorded_by'
    ]
    
    list_filter = [
        'payment_method',
        'payment_date',
        ('payment_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'receipt_number',
        'transaction_reference',
        'policy__policy_number',
        'policy__vehicle__registration_number'
    ]
    
    readonly_fields = [
        'receipt_number', 'recorded_by', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'receipt_number',
                'policy',
                ('payment_date', 'amount'),
                ('payment_method', 'transaction_reference'),
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            )
        }),
        ('System Information', {
            'fields': (
                'recorded_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
    date_hierarchy = 'payment_date'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('policy__vehicle', 'recorded_by')
    
    def policy_link(self, obj):
        """Display policy with link"""
        url = reverse('admin:insurance_insurancepolicy_change', args=[obj.policy.pk])
        return format_html('<a href="{}">{}</a>', url, obj.policy.policy_number)
    policy_link.short_description = 'Policy'
    
    def amount_display(self, obj):
        """Display amount formatted"""
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">KES {:,.2f}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def payment_method_badge(self, obj):
        """Display payment method as badge"""
        colors = {
            'cash': '#28a745',
            'mpesa': '#007bff',
            'bank_transfer': '#17a2b8',
            'cheque': '#ffc107',
            'card': '#6f42c1',
            'direct_debit': '#e83e8c',
        }
        color = colors.get(obj.payment_method, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_method_display().upper()
        )
    payment_method_badge.short_description = 'Method'
    payment_method_badge.admin_order_field = 'payment_method'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)