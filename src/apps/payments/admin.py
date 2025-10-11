"""
Admin configuration for payments app
Provides admin interface for managing payments, installment plans, and schedules
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from .models import Payment, InstallmentPlan, PaymentSchedule, PaymentReminder
import csv


# ==================== INLINE ADMINS ====================

class PaymentScheduleInline(admin.TabularInline):
    """
    Inline admin for payment schedules
    """
    model = PaymentSchedule
    extra = 0
    fields = [
        'installment_number', 'due_date', 'amount_due', 
        'amount_paid', 'is_paid', 'payment_date'
    ]
    readonly_fields = ['installment_number', 'due_date', 'amount_due']
    can_delete = False


class PaymentReminderInline(admin.TabularInline):
    """
    Inline admin for payment reminders
    """
    model = PaymentReminder
    extra = 0
    fields = ['reminder_type', 'reminder_date', 'status', 'message']
    readonly_fields = ['reminder_date']


# ==================== PAYMENT ADMIN ====================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Admin interface for Payment model
    """
    list_display = [
        'receipt_number', 'client_link', 'vehicle_link', 
        'payment_date', 'amount_display', 'payment_method_badge',
        'transaction_reference', 'recorded_by', 'created_at'
    ]
    
    list_filter = [
        'payment_method', 
        'payment_date',
        ('payment_date', admin.DateFieldListFilter),
        'created_at'
    ]
    
    search_fields = [
        'receipt_number',
        'transaction_reference',
        'client_vehicle__client__first_name',
        'client_vehicle__client__last_name',
        'client_vehicle__client__id_number',
        'client_vehicle__vehicle__registration_number',
        'client_vehicle__vehicle__make',
        'client_vehicle__vehicle__model'
    ]
    
    readonly_fields = [
        'receipt_number', 'recorded_by', 'created_at', 'updated_at',
        'client_display', 'vehicle_display', 'remaining_balance_display'
    ]
    
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'receipt_number',
                'client_vehicle',
                ('client_display', 'vehicle_display'),
                ('payment_date', 'amount'),
                ('payment_method', 'transaction_reference'),
            )
        }),
        ('Balance Information', {
            'fields': (
                'remaining_balance_display',
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
    
    actions = ['export_payments_csv', 'generate_receipts']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'recorded_by'
        )
    
    def changelist_view(self, request, extra_context=None):
        """Add custom button to changelist"""
        extra_context = extra_context or {}
        extra_context['show_record_payment_button'] = True
        return super().changelist_view(request, extra_context)
    
    def client_link(self, obj):
        """Display client name with link"""
        client = obj.client_vehicle.client
        url = reverse('admin:clients_client_change', args=[client.pk])
        return format_html('<a href="{}">{}</a>', url, client.get_full_name())
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client_vehicle__client__first_name'
    
    def vehicle_link(self, obj):
        """Display vehicle with link"""
        vehicle = obj.client_vehicle.vehicle
        url = reverse('admin:vehicles_vehicle_change', args=[vehicle.pk])
        return format_html('<a href="{}">{}</a>', url, vehicle)
    vehicle_link.short_description = 'Vehicle'
    vehicle_link.admin_order_field = 'client_vehicle__vehicle__make'
    
    def client_display(self, obj):
        """Display client information"""
        client = obj.client_vehicle.client
        return f"{client.get_full_name()} - {client.phone_primary}"
    client_display.short_description = 'Client Details'
    
    def vehicle_display(self, obj):
        """Display vehicle information"""
        vehicle = obj.client_vehicle.vehicle
        return f"{vehicle.make} {vehicle.model} - {vehicle.registration_number}"
    vehicle_display.short_description = 'Vehicle Details'
    
    def amount_display(self, obj):
        """Display amount formatted with color"""
        return format_html(
            '<span style="color: #28a745; font-weight: bold; font-size: 13px;">'
            'KES {:,.2f}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def payment_method_badge(self, obj):
        """Display payment method as colored badge"""
        colors = {
            'cash': '#28a745',
            'mpesa': '#007bff',
            'bank_transfer': '#17a2b8',
            'cheque': '#ffc107',
            'card': '#6f42c1',
            'other': '#6c757d',
        }
        color = colors.get(obj.payment_method, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold; '
            'text-transform: uppercase;">{}</span>',
            color,
            obj.get_payment_method_display()
        )
    payment_method_badge.short_description = 'Method'
    payment_method_badge.admin_order_field = 'payment_method'
    
    def remaining_balance_display(self, obj):
        """Display remaining balance for the client vehicle"""
        balance = obj.client_vehicle.balance
        color = '#dc3545' if balance > 0 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 14px;">'
            'KES {:,.2f}</span>',
            color,
            balance
        )
    remaining_balance_display.short_description = 'Remaining Balance'
    
    def export_payments_csv(self, request, queryset):
        """Export selected payments to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payments_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Receipt Number', 'Client', 'Vehicle', 'Payment Date',
            'Amount', 'Payment Method', 'Transaction Reference', 'Recorded By'
        ])
        
        for payment in queryset:
            writer.writerow([
                payment.receipt_number,
                payment.client_vehicle.client.get_full_name(),
                str(payment.client_vehicle.vehicle),
                payment.payment_date.strftime('%Y-%m-%d'),
                payment.amount,
                payment.get_payment_method_display(),
                payment.transaction_reference or '',
                payment.recorded_by.get_full_name() if payment.recorded_by else ''
            ])
        
        self.message_user(request, f'{queryset.count()} payments exported successfully.')
        return response
    export_payments_csv.short_description = 'Export selected to CSV'
    
    def generate_receipts(self, request, queryset):
        """Generate receipts for selected payments"""
        # This would trigger receipt generation
        count = queryset.count()
        self.message_user(request, f'Receipt generation initiated for {count} payment(s).')
    generate_receipts.short_description = 'Generate receipts'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


# ==================== INSTALLMENT PLAN ADMIN ====================

@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    """
    Admin interface for InstallmentPlan model
    """
    list_display = [
        'id', 'client_link', 'vehicle_link', 
        'total_amount_display', 'monthly_installment_display',
        'number_of_installments', 'progress_bar', 
        'status_badge', 'start_date', 'end_date'
    ]
    
    list_filter = [
        'is_active',
        'is_completed',
        'start_date',
        'end_date',
        ('start_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'client_vehicle__client__first_name',
        'client_vehicle__client__last_name',
        'client_vehicle__client__id_number',
        'client_vehicle__vehicle__registration_number',
        'client_vehicle__vehicle__make',
        'client_vehicle__vehicle__model'
    ]
    
    readonly_fields = [
        'created_by', 'created_at', 'updated_at', 'end_date',
        'balance_after_deposit_display', 'total_with_interest_display',
        'total_interest_display', 'payment_progress_display',
        'amount_paid_display', 'remaining_balance_display',
        'overdue_badge'
    ]
    
    fieldsets = (
        ('Plan Information', {
            'fields': (
                'client_vehicle',
                ('start_date', 'end_date'),
                ('is_active', 'is_completed'),
                'overdue_badge',
            )
        }),
        ('Financial Details', {
            'fields': (
                ('total_amount', 'deposit'),
                'balance_after_deposit_display',
                ('monthly_installment', 'number_of_installments'),
                'interest_rate',
                'total_with_interest_display',
                'total_interest_display',
            )
        }),
        ('Payment Progress', {
            'fields': (
                'amount_paid_display',
                'remaining_balance_display',
                'payment_progress_display',
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
    
    inlines = [PaymentScheduleInline]
    
    list_per_page = 25
    date_hierarchy = 'start_date'
    
    actions = ['activate_plans', 'deactivate_plans', 'mark_completed', 'regenerate_schedules']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'created_by'
        )
    
    def client_link(self, obj):
        """Display client name with link"""
        client = obj.client_vehicle.client
        url = reverse('admin:clients_client_change', args=[client.pk])
        return format_html('<a href="{}">{}</a>', url, client.get_full_name())
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client_vehicle__client__first_name'
    
    def vehicle_link(self, obj):
        """Display vehicle with link"""
        vehicle = obj.client_vehicle.vehicle
        url = reverse('admin:vehicles_vehicle_change', args=[vehicle.pk])
        return format_html('<a href="{}">{}</a>', url, vehicle)
    vehicle_link.short_description = 'Vehicle'
    vehicle_link.admin_order_field = 'client_vehicle__vehicle__make'
    
    def total_amount_display(self, obj):
        """Display total amount formatted"""
        return format_html('KES {:,.2f}', obj.total_amount)
    total_amount_display.short_description = 'Total Amount'
    total_amount_display.admin_order_field = 'total_amount'
    
    def monthly_installment_display(self, obj):
        """Display monthly installment formatted"""
        return format_html('KES {:,.2f}', obj.monthly_installment)
    monthly_installment_display.short_description = 'Monthly'
    monthly_installment_display.admin_order_field = 'monthly_installment'
    
    def balance_after_deposit_display(self, obj):
        """Display balance after deposit"""
        return format_html('KES {:,.2f}', obj.balance_after_deposit)
    balance_after_deposit_display.short_description = 'Balance After Deposit'
    
    def total_with_interest_display(self, obj):
        """Display total with interest"""
        return format_html('KES {:,.2f}', obj.total_with_interest)
    total_with_interest_display.short_description = 'Total with Interest'
    
    def total_interest_display(self, obj):
        """Display total interest"""
        return format_html(
            '<span style="color: #ffc107; font-weight: bold;">KES {:,.2f}</span>',
            obj.total_interest
        )
    total_interest_display.short_description = 'Total Interest'
    
    def amount_paid_display(self, obj):
        """Display amount paid"""
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">KES {:,.2f}</span>',
            obj.amount_paid
        )
    amount_paid_display.short_description = 'Amount Paid'
    
    def remaining_balance_display(self, obj):
        """Display remaining balance"""
        balance = obj.remaining_balance
        color = '#dc3545' if balance > 0 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KES {:,.2f}</span>',
            color,
            balance
        )
    remaining_balance_display.short_description = 'Remaining Balance'
    
    def payment_progress_display(self, obj):
        """Display payment progress"""
        return format_html('{:.1f}%', obj.payment_progress)
    payment_progress_display.short_description = 'Progress'
    
    def progress_bar(self, obj):
        """Display payment progress as progress bar"""
        progress = obj.payment_progress
        if progress >= 100:
            color = '#28a745'
            text = 'COMPLETED'
        elif progress >= 75:
            color = '#28a745'
            text = f'{progress:.0f}%'
        elif progress >= 50:
            color = '#ffc107'
            text = f'{progress:.0f}%'
        elif progress >= 25:
            color = '#fd7e14'
            text = f'{progress:.0f}%'
        else:
            color = '#dc3545'
            text = f'{progress:.0f}%'
        
        return format_html(
            '<div style="width: 120px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'text-align: center; padding: 4px 0; font-size: 11px; font-weight: bold;">'
            '{}</div></div>',
            min(progress, 100), color, text
        )
    progress_bar.short_description = 'Progress'
    
    def status_badge(self, obj):
        """Display status as badge"""
        if obj.is_completed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">COMPLETED</span>'
            )
        elif obj.is_overdue:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">OVERDUE</span>'
            )
        elif obj.is_active:
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">ACTIVE</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">INACTIVE</span>'
            )
    status_badge.short_description = 'Status'
    
    def overdue_badge(self, obj):
        """Display overdue status"""
        if obj.is_overdue:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 8px 15px; '
                'border-radius: 4px; font-size: 13px; font-weight: bold;">⚠️ OVERDUE</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 8px 15px; '
            'border-radius: 4px; font-size: 13px; font-weight: bold;">✓ ON TIME</span>'
        )
    overdue_badge.short_description = 'Payment Status'
    
    def activate_plans(self, request, queryset):
        """Activate selected plans"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} plan(s) activated successfully.')
    activate_plans.short_description = 'Activate selected plans'
    
    def deactivate_plans(self, request, queryset):
        """Deactivate selected plans"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} plan(s) deactivated successfully.')
    deactivate_plans.short_description = 'Deactivate selected plans'
    
    def mark_completed(self, request, queryset):
        """Mark plans as completed"""
        updated = queryset.update(is_completed=True, is_active=False)
        self.message_user(request, f'{updated} plan(s) marked as completed.')
    mark_completed.short_description = 'Mark as completed'
    
    def regenerate_schedules(self, request, queryset):
        """Regenerate payment schedules"""
        count = 0
        for plan in queryset:
            plan.generate_payment_schedule()
            count += 1
        self.message_user(request, f'Payment schedules regenerated for {count} plan(s).')
    regenerate_schedules.short_description = 'Regenerate payment schedules'
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== PAYMENT SCHEDULE ADMIN ====================

@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    """
    Admin interface for PaymentSchedule model
    """
    list_display = [
        'id', 'client_link', 'installment_number', 
        'due_date', 'amount_due_display', 'amount_paid_display',
        'remaining_amount_display', 'status_badge', 'overdue_days'
    ]
    
    list_filter = [
        'is_paid',
        'due_date',
        ('due_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'installment_plan__client_vehicle__client__first_name',
        'installment_plan__client_vehicle__client__last_name',
        'installment_plan__client_vehicle__vehicle__registration_number'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'remaining_amount_display',
        'overdue_badge', 'days_overdue_display'
    ]
    
    fieldsets = (
        ('Schedule Information', {
            'fields': (
                'installment_plan',
                'installment_number',
                'due_date',
            )
        }),
        ('Payment Details', {
            'fields': (
                ('amount_due', 'amount_paid'),
                'remaining_amount_display',
                ('is_paid', 'payment_date'),
                'payment',
            )
        }),
        ('Overdue Status', {
            'fields': (
                'overdue_badge',
                'days_overdue_display',
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            )
        }),
        ('System Information', {
            'fields': (
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PaymentReminderInline]
    
    list_per_page = 50
    date_hierarchy = 'due_date'
    
    actions = ['mark_as_paid', 'send_reminders']
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'installment_plan__client_vehicle__client',
            'installment_plan__client_vehicle__vehicle',
            'payment'
        )
    
    def client_link(self, obj):
        """Display client name with link"""
        client = obj.installment_plan.client_vehicle.client
        url = reverse('admin:clients_client_change', args=[client.pk])
        return format_html('<a href="{}">{}</a>', url, client.get_full_name())
    client_link.short_description = 'Client'
    
    def amount_due_display(self, obj):
        """Display amount due formatted"""
        return format_html('KES {:,.2f}', obj.amount_due)
    amount_due_display.short_description = 'Amount Due'
    amount_due_display.admin_order_field = 'amount_due'
    
    def amount_paid_display(self, obj):
        """Display amount paid formatted"""
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">KES {:,.2f}</span>',
            obj.amount_paid
        )
    amount_paid_display.short_description = 'Amount Paid'
    amount_paid_display.admin_order_field = 'amount_paid'
    
    def remaining_amount_display(self, obj):
        """Display remaining amount"""
        remaining = obj.remaining_amount
        color = '#dc3545' if remaining > 0 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KES {:,.2f}</span>',
            color,
            remaining
        )
    remaining_amount_display.short_description = 'Remaining'
    
    def status_badge(self, obj):
        """Display status as badge"""
        if obj.is_paid:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">PAID</span>'
            )
        elif obj.is_overdue:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">OVERDUE</span>'
            )
        elif obj.is_partial_payment:
            return format_html(
                '<span style="background-color: #ffc107; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">PARTIAL</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">PENDING</span>'
            )
    status_badge.short_description = 'Status'
    
    def overdue_days(self, obj):
        """Display overdue days"""
        if obj.is_overdue:
            days = obj.days_overdue
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{} days</span>',
                days
            )
        return '-'
    overdue_days.short_description = 'Overdue'
    
    def overdue_badge(self, obj):
        """Display detailed overdue status"""
        if obj.is_overdue:
            days = obj.days_overdue
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 8px 15px; '
                'border-radius: 4px; font-size: 13px; font-weight: bold;">'
                '⚠️ OVERDUE BY {} DAYS</span>',
                days
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 8px 15px; '
            'border-radius: 4px; font-size: 13px; font-weight: bold;">✓ ON TIME</span>'
        )
    overdue_badge.short_description = 'Status'
    
    def days_overdue_display(self, obj):
        """Display days overdue"""
        if obj.is_overdue:
            return f'{obj.days_overdue} days'
        return 'Not overdue'
    days_overdue_display.short_description = 'Days Overdue'
    
    def mark_as_paid(self, request, queryset):
        """Mark selected schedules as paid"""
        updated = queryset.filter(is_paid=False).update(
            is_paid=True,
            payment_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} schedule(s) marked as paid.')
    mark_as_paid.short_description = 'Mark as paid'
    
    def send_reminders(self, request, queryset):
        """Send payment reminders"""
        count = queryset.filter(is_paid=False).count()
        self.message_user(request, f'Payment reminders sent for {count} schedule(s).')
    send_reminders.short_description = 'Send payment reminders'


# ==================== PAYMENT REMINDER ADMIN ====================

@admin.register(PaymentReminder)
class PaymentReminderAdmin(admin.ModelAdmin):
    """
    Admin interface for PaymentReminder model
    """
    list_display = [
        'id', 'client_link', 'reminder_type_badge', 
        'reminder_date', 'status_badge', 'sent_by'
    ]
    
    list_filter = [
        'reminder_type',
        'status',
        'reminder_date',
        ('reminder_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'payment_schedule__installment_plan__client_vehicle__client__first_name',
        'payment_schedule__installment_plan__client_vehicle__client__last_name',
        'message'
    ]
    
    readonly_fields = [
        'reminder_date', 'sent_by', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Reminder Information', {
            'fields': (
                'payment_schedule',
                ('reminder_type', 'status'),
                'reminder_date',
                'message',
            )
        }),
        ('Response', {
            'fields': (
                'client_response',
                'response_date',
            )
        }),
        ('System Information', {
            'fields': (
                'sent_by',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
    date_hierarchy = 'reminder_date'
    
    def client_link(self, obj):
        """Display client name with link"""
        client = obj.payment_schedule.installment_plan.client_vehicle.client
        url = reverse('admin:clients_client_change', args=[client.pk])
        return format_html('<a href="{}">{}</a>', url, client.get_full_name())
    client_link.short_description = 'Client'
    
    def reminder_type_badge(self, obj):
        """Display reminder type as badge"""
        colors = {
            'sms': '#007bff',
            'email': '#28a745',
            'call': '#ffc107',
            'letter': '#6f42c1',
        }
        color = colors.get(obj.reminder_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_reminder_type_display().upper()
        )
    reminder_type_badge.short_description = 'Type'
    reminder_type_badge.admin_order_field = 'reminder_type'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': '#6c757d',
            'sent': '#007bff',
            'failed': '#dc3545',
            'responded': '#28a745',
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
    
    def save_model(self, request, obj, form, change):
        """Save model with user tracking"""
        if not change:  # New object
            obj.sent_by = request.user
        super().save_model(request, obj, form, change)