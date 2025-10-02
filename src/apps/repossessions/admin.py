"""
Admin configuration for the repossessions app.
Provides comprehensive repossession management interface in Django admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count

from .models import (
    Repossession, RepossessionDocument, RepossessionNote,
    RepossessionExpense, RepossessionStatusHistory, RepossessionNotice,
    RepossessionContact, RepossessionRecoveryAttempt
)


class RepossessionDocumentInline(admin.TabularInline):
    """Inline admin for repossession documents."""
    model = RepossessionDocument
    extra = 0
    readonly_fields = ('uploaded_by', 'uploaded_at', 'file_size', 'file_type')
    fields = ('document_type', 'title', 'file', 'uploaded_by', 'uploaded_at')


class RepossessionNoteInline(admin.TabularInline):
    """Inline admin for repossession notes."""
    model = RepossessionNote
    extra = 0
    readonly_fields = ('created_by', 'created_at')
    fields = ('note', 'note_type', 'is_important', 'created_by', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        return True


class RepossessionExpenseInline(admin.TabularInline):
    """Inline admin for repossession expenses."""
    model = RepossessionExpense
    extra = 0
    readonly_fields = ('created_by', 'created_at')
    fields = ('expense_type', 'description', 'amount', 'expense_date', 'paid')


class RepossessionStatusHistoryInline(admin.TabularInline):
    """Inline admin for status history."""
    model = RepossessionStatusHistory
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'changed_at')
    fields = ('old_status', 'new_status', 'changed_by', 'changed_at', 'reason')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Repossession)
class RepossessionAdmin(admin.ModelAdmin):
    """Admin interface for repossessions."""
    
    list_display = (
        'repossession_number', 'vehicle_link', 'client_link',
        'status_badge', 'reason', 'outstanding_amount',
        'days_in_process_display', 'assigned_to', 'initiated_date'
    )
    
    list_filter = (
        'status', 'reason', 'legal_notice_sent', 'court_order_obtained',
        'initiated_date', 'resolution_type'
    )
    
    search_fields = (
        'repossession_number', 'vehicle__registration_number',
        'vehicle__make', 'vehicle__model', 'client__name',
        'client__email', 'last_known_location'
    )
    
    readonly_fields = (
        'repossession_number', 'total_cost', 'created_by',
        'created_at', 'updated_at', 'days_in_process_display',
        'total_amount_due_display'
    )
    
    autocomplete_fields = ['vehicle', 'client', 'assigned_to']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'repossession_number', 'vehicle', 'client',
                'reason', 'status'
            )
        }),
        ('Financial Details', {
            'fields': (
                'outstanding_amount', 'payments_missed',
                'last_payment_date', 'total_amount_due_display'
            )
        }),
        ('Important Dates', {
            'fields': (
                'initiated_date', 'notice_sent_date',
                'recovery_date', 'completion_date'
            )
        }),
        ('Assignment & Location', {
            'fields': (
                'assigned_to', 'last_known_location', 'current_location'
            )
        }),
        ('Recovery Details', {
            'fields': (
                'recovery_method', 'recovery_agent'
            ),
            'classes': ('collapse',)
        }),
        ('Legal Information', {
            'fields': (
                'legal_notice_sent', 'legal_notice_date',
                'court_order_obtained', 'court_order_date',
                'court_order_number'
            ),
            'classes': ('collapse',)
        }),
        ('Costs', {
            'fields': (
                'recovery_cost', 'storage_cost', 'legal_cost',
                'other_costs', 'total_cost'
            ),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': (
                'resolution_type', 'resolution_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': (
                'notes', 'created_by', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [
        RepossessionStatusHistoryInline,
        RepossessionDocumentInline,
        RepossessionNoteInline,
        RepossessionExpenseInline
    ]
    
    date_hierarchy = 'initiated_date'
    
    actions = [
        'mark_as_in_progress', 'mark_as_recovered',
        'mark_as_completed', 'export_to_csv'
    ]
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'vehicle', 'client', 'assigned_to', 'created_by'
        )
    
    def vehicle_link(self, obj):
        """Display vehicle as clickable link."""
        url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.vehicle
        )
    vehicle_link.short_description = 'Vehicle'
    vehicle_link.admin_order_field = 'vehicle'
    
    def client_link(self, obj):
        """Display client as clickable link."""
        url = reverse('admin:clients_client_change', args=[obj.client.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.client
        )
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PENDING': '#ffc107',
            'NOTICE_SENT': '#17a2b8',
            'IN_PROGRESS': '#007bff',
            'VEHICLE_RECOVERED': '#28a745',
            'COMPLETED': '#6c757d',
            'CANCELLED': '#dc3545',
            'ON_HOLD': '#fd7e14',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def days_in_process_display(self, obj):
        """Display days in process."""
        days = obj.get_days_in_process()
        if days > 30:
            color = 'red'
        elif days > 14:
            color = 'orange'
        else:
            color = 'green'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} days</span>',
            color, days
        )
    days_in_process_display.short_description = 'Days in Process'
    
    def total_amount_due_display(self, obj):
        """Display total amount including costs."""
        return f"KES {obj.get_total_amount_due():,.2f}"
    total_amount_due_display.short_description = 'Total Amount Due'
    
    def save_model(self, request, obj, form, change):
        """Set created_by on creation."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    # Admin Actions
    @admin.action(description='Mark as In Progress')
    def mark_as_in_progress(self, request, queryset):
        """Mark repossessions as in progress."""
        updated = queryset.filter(status='NOTICE_SENT').update(status='IN_PROGRESS')
        self.message_user(request, f'{updated} repossession(s) marked as in progress.')
    
    @admin.action(description='Mark as Vehicle Recovered')
    def mark_as_recovered(self, request, queryset):
        """Mark vehicles as recovered."""
        count = 0
        for repo in queryset.filter(status='IN_PROGRESS'):
            repo.mark_as_recovered()
            count += 1
        self.message_user(request, f'{count} vehicle(s) marked as recovered.')
    
    @admin.action(description='Mark as Completed')
    def mark_as_completed(self, request, queryset):
        """Mark repossessions as completed."""
        count = 0
        for repo in queryset.filter(status='VEHICLE_RECOVERED'):
            repo.mark_as_completed('OTHER', 'Completed via admin action')
            count += 1
        self.message_user(request, f'{count} repossession(s) marked as completed.')
    
    @admin.action(description='Export to CSV')
    def export_to_csv(self, request, queryset):
        """Export repossessions to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="repossessions.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Repossession Number', 'Vehicle', 'Client', 'Status',
            'Reason', 'Outstanding Amount', 'Total Cost',
            'Initiated Date', 'Days in Process', 'Assigned To'
        ])
        
        for repo in queryset:
            writer.writerow([
                repo.repossession_number,
                str(repo.vehicle),
                repo.client.name if hasattr(repo.client, 'name') else str(repo.client),
                repo.get_status_display(),
                repo.get_reason_display(),
                repo.outstanding_amount,
                repo.total_cost,
                repo.initiated_date.strftime('%Y-%m-%d'),
                repo.get_days_in_process(),
                repo.assigned_to.get_full_name() if repo.assigned_to else '',
            ])
        
        return response


@admin.register(RepossessionDocument)
class RepossessionDocumentAdmin(admin.ModelAdmin):
    """Admin interface for repossession documents."""
    
    list_display = (
        'repossession_link', 'document_type', 'title',
        'file_size_display', 'uploaded_by', 'uploaded_at'
    )
    
    list_filter = ('document_type', 'uploaded_at')
    
    search_fields = (
        'repossession__repossession_number', 'title', 'description'
    )
    
    readonly_fields = ('uploaded_by', 'uploaded_at', 'file_size', 'file_type')
    
    date_hierarchy = 'uploaded_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'uploaded_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'
    
    def file_size_display(self, obj):
        """Display formatted file size."""
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'


@admin.register(RepossessionNote)
class RepossessionNoteAdmin(admin.ModelAdmin):
    """Admin interface for repossession notes."""
    
    list_display = (
        'repossession_link', 'note_preview', 'note_type',
        'is_important', 'created_by', 'created_at'
    )
    
    list_filter = ('note_type', 'is_important', 'created_at')
    
    search_fields = (
        'repossession__repossession_number', 'note'
    )
    
    readonly_fields = ('created_by', 'created_at')
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'created_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'
    
    def note_preview(self, obj):
        """Display truncated note."""
        return obj.note[:100] + '...' if len(obj.note) > 100 else obj.note
    note_preview.short_description = 'Note'


@admin.register(RepossessionExpense)
class RepossessionExpenseAdmin(admin.ModelAdmin):
    """Admin interface for repossession expenses."""
    
    list_display = (
        'repossession_link', 'expense_type', 'description',
        'amount', 'expense_date', 'paid', 'vendor'
    )
    
    list_filter = ('expense_type', 'paid', 'expense_date')
    
    search_fields = (
        'repossession__repossession_number', 'description',
        'vendor', 'receipt_number'
    )
    
    readonly_fields = ('created_by', 'created_at')
    
    date_hierarchy = 'expense_date'
    
    actions = ['mark_as_paid']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'created_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'
    
    @admin.action(description='Mark as paid')
    def mark_as_paid(self, request, queryset):
        """Mark expenses as paid."""
        from datetime import date
        updated = queryset.update(paid=True, payment_date=date.today())
        self.message_user(request, f'{updated} expense(s) marked as paid.')


@admin.register(RepossessionNotice)
class RepossessionNoticeAdmin(admin.ModelAdmin):
    """Admin interface for repossession notices."""
    
    list_display = (
        'repossession_link', 'notice_type', 'notice_date',
        'delivery_method', 'delivered', 'response_received',
        'is_overdue_display'
    )
    
    list_filter = (
        'notice_type', 'delivery_method', 'delivered',
        'response_received', 'notice_date'
    )
    
    search_fields = (
        'repossession__repossession_number', 'delivery_address',
        'tracking_number', 'received_by'
    )
    
    readonly_fields = ('sent_by', 'created_at')
    
    date_hierarchy = 'notice_date'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'sent_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'
    
    def is_overdue_display(self, obj):
        """Display if response is overdue."""
        if obj.is_overdue():
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ OVERDUE</span>'
            )
        return format_html(
            '<span style="color: green;">✓ On Track</span>'
        )
    is_overdue_display.short_description = 'Response Status'


@admin.register(RepossessionContact)
class RepossessionContactAdmin(admin.ModelAdmin):
    """Admin interface for repossession contacts."""
    
    list_display = (
        'repossession_link', 'contact_date', 'contact_method',
        'contacted_person', 'outcome', 'follow_up_date'
    )
    
    list_filter = ('contact_method', 'outcome', 'contact_date')
    
    search_fields = (
        'repossession__repossession_number', 'contacted_person',
        'discussion_summary'
    )
    
    readonly_fields = ('created_by',)
    
    date_hierarchy = 'contact_date'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'created_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'


@admin.register(RepossessionRecoveryAttempt)
class RepossessionRecoveryAttemptAdmin(admin.ModelAdmin):
    """Admin interface for recovery attempts."""
    
    list_display = (
        'repossession_link', 'attempt_date', 'agent_name',
        'result_badge', 'police_involved', 'cost_incurred'
    )
    
    list_filter = ('result', 'police_involved', 'attempt_date')
    
    search_fields = (
        'repossession__repossession_number', 'agent_name',
        'location', 'details'
    )
    
    readonly_fields = ('created_by',)
    
    date_hierarchy = 'attempt_date'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'created_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'
    
    def result_badge(self, obj):
        """Display result as colored badge."""
        color_map = {
            'SUCCESSFUL': '#28a745',
            'NOT_FOUND': '#ffc107',
            'ACCESS_DENIED': '#dc3545',
            'CONFRONTATION': '#dc3545',
            'POLICE_CALLED': '#17a2b8',
            'POSTPONED': '#6c757d',
            'OTHER': '#6c757d',
        }
        color = color_map.get(obj.result, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_result_display()
        )
    result_badge.short_description = 'Result'


@admin.register(RepossessionStatusHistory)
class RepossessionStatusHistoryAdmin(admin.ModelAdmin):
    """Admin interface for status history."""
    
    list_display = (
        'repossession_link', 'old_status', 'new_status',
        'changed_by', 'changed_at'
    )
    
    list_filter = ('old_status', 'new_status', 'changed_at')
    
    search_fields = ('repossession__repossession_number', 'reason')
    
    readonly_fields = ('repossession', 'old_status', 'new_status', 'changed_by', 'changed_at')
    
    date_hierarchy = 'changed_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('repossession', 'changed_by')
    
    def repossession_link(self, obj):
        """Display repossession as clickable link."""
        url = reverse('admin:repossessions_repossession_change', args=[obj.repossession.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.repossession.repossession_number
        )
    repossession_link.short_description = 'Repossession'