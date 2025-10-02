"""
Admin configuration for the expenses app.
Provides comprehensive expense management interface in Django admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal

from .models import (
    Expense, ExpenseCategory, ExpenseReceipt, ExpenseReport,
    ExpenseReportItem, ExpenseTag, RecurringExpense, ExpenseApprovalWorkflow
)


class ExpenseReceiptInline(admin.TabularInline):
    """Inline admin for expense receipts."""
    model = ExpenseReceipt
    extra = 0
    readonly_fields = ('uploaded_by', 'uploaded_at', 'file_size', 'file_type')
    fields = ('file', 'description', 'uploaded_by', 'uploaded_at', 'file_size')
    
    def has_add_permission(self, request, obj=None):
        """Control add permission."""
        return True


class ExpenseApprovalWorkflowInline(admin.TabularInline):
    """Inline admin for approval workflow."""
    model = ExpenseApprovalWorkflow
    extra = 0
    readonly_fields = ('actioned_at', 'created_at')
    fields = ('approver', 'level', 'status', 'comments', 'actioned_at')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Admin interface for expenses."""
    
    list_display = (
        'title', 'category_link', 'amount_display', 'status_badge',
        'submitted_by', 'expense_date', 'is_reimbursable', 
        'reimbursed', 'created_at'
    )
    
    list_filter = (
        'status', 'is_reimbursable', 'reimbursed', 'category',
        'expense_date', 'payment_method', 'created_at'
    )
    
    search_fields = (
        'title', 'description', 'vendor_name', 'invoice_number',
        'submitted_by__username', 'submitted_by__email'
    )
    
    readonly_fields = (
        'total_amount', 'submitted_by', 'created_at', 'updated_at',
        'approved_by', 'approved_at', 'reimbursement_date'
    )
    
    autocomplete_fields = ['related_vehicle', 'related_client', 'tags']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title', 'description', 'category', 'tags'
            )
        }),
        ('Financial Details', {
            'fields': (
                'amount', 'currency', 'tax_amount', 'total_amount'
            )
        }),
        ('Payment Information', {
            'fields': (
                'expense_date', 'payment_method', 'vendor_name', 'invoice_number'
            )
        }),
        ('Relationships', {
            'fields': (
                'related_vehicle', 'related_client'
            ),
            'classes': ('collapse',)
        }),
        ('Status & Approval', {
            'fields': (
                'status', 'submitted_by', 'approved_by', 'approved_at',
                'rejection_reason'
            )
        }),
        ('Reimbursement', {
            'fields': (
                'is_reimbursable', 'reimbursed', 'reimbursement_date',
                'reimbursement_reference'
            ),
            'classes': ('collapse',)
        }),
        ('Recurring', {
            'fields': (
                'is_recurring', 'recurring_frequency'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': (
                'notes', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ExpenseReceiptInline, ExpenseApprovalWorkflowInline]
    
    date_hierarchy = 'expense_date'
    
    actions = [
        'approve_expenses', 'reject_expenses', 'mark_as_paid',
        'mark_as_reimbursed', 'export_to_csv'
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'submitted_by', 'category', 'approved_by', 
            'related_vehicle', 'related_client'
        ).prefetch_related('tags', 'receipts')
    
    def category_link(self, obj):
        """Display category as clickable link."""
        if obj.category:
            url = reverse('admin:expenses_expensecategory_change', args=[obj.category.pk])
            return format_html('<a href="{}">{}</a>', url, obj.category.name)
        return '-'
    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'
    
    def amount_display(self, obj):
        """Display formatted amount with currency."""
        return format_html(
            '<strong>{} {}</strong>',
            obj.currency, obj.total_amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'total_amount'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'DRAFT': '#6c757d',
            'SUBMITTED': '#007bff',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'PAID': '#17a2b8',
            'CANCELLED': '#6c757d',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def save_model(self, request, obj, form, change):
        """Set submitted_by on creation."""
        if not change:
            obj.submitted_by = request.user
        super().save_model(request, obj, form, change)
    
    # Admin Actions
    @admin.action(description='Approve selected expenses')
    def approve_expenses(self, request, queryset):
        """Approve expenses."""
        queryset = queryset.filter(status='SUBMITTED')
        count = 0
        for expense in queryset:
            if expense.approve(request.user):
                count += 1
        self.message_user(request, f'{count} expense(s) approved.')
    
    @admin.action(description='Reject selected expenses')
    def reject_expenses(self, request, queryset):
        """Reject expenses."""
        queryset = queryset.filter(status='SUBMITTED')
        count = 0
        for expense in queryset:
            if expense.reject(request.user, 'Rejected via admin action'):
                count += 1
        self.message_user(request, f'{count} expense(s) rejected.')
    
    @admin.action(description='Mark selected as paid')
    def mark_as_paid(self, request, queryset):
        """Mark expenses as paid."""
        queryset = queryset.filter(status='APPROVED')
        count = 0
        for expense in queryset:
            if expense.mark_as_paid():
                count += 1
        self.message_user(request, f'{count} expense(s) marked as paid.')
    
    @admin.action(description='Mark as reimbursed')
    def mark_as_reimbursed(self, request, queryset):
        """Mark expenses as reimbursed."""
        updated = queryset.filter(
            is_reimbursable=True,
            reimbursed=False,
            status='PAID'
        ).update(
            reimbursed=True,
            reimbursement_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} expense(s) marked as reimbursed.')
    
    @admin.action(description='Export to CSV')
    def export_to_csv(self, request, queryset):
        """Export expenses to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'Category', 'Amount', 'Currency', 'Tax', 'Total',
            'Status', 'Submitted By', 'Expense Date', 'Payment Method',
            'Vendor', 'Invoice Number', 'Reimbursable', 'Reimbursed'
        ])
        
        for expense in queryset:
            writer.writerow([
                expense.id,
                expense.title,
                expense.category.name if expense.category else '',
                expense.amount,
                expense.currency,
                expense.tax_amount,
                expense.total_amount,
                expense.get_status_display(),
                expense.submitted_by.username,
                expense.expense_date.strftime('%Y-%m-%d'),
                expense.get_payment_method_display(),
                expense.vendor_name,
                expense.invoice_number,
                expense.is_reimbursable,
                expense.reimbursed,
            ])
        
        return response


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """Admin interface for expense categories."""
    
    list_display = (
        'name_with_icon', 'code', 'parent', 'budget_limit',
        'expense_count', 'total_spent', 'is_active'
    )
    
    list_filter = ('is_active', 'requires_receipt', 'requires_approval', 'parent')
    
    search_fields = ('name', 'code', 'description')
    
    readonly_fields = ('expense_count', 'total_spent', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'code', 'parent', 'is_active')
        }),
        ('Requirements', {
            'fields': ('requires_receipt', 'requires_approval')
        }),
        ('Budget', {
            'fields': ('budget_limit',)
        }),
        ('Display', {
            'fields': ('icon', 'color')
        }),
        ('Statistics', {
            'fields': ('expense_count', 'total_spent', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add annotations."""
        qs = super().get_queryset(request)
        return qs.annotate(
            exp_count=Count('expenses'),
            exp_total=Sum('expenses__total_amount')
        )
    
    def name_with_icon(self, obj):
        """Display name with icon and color."""
        if obj.icon:
            return format_html(
                '<span style="color: {}"><i class="{}"></i> {}</span>',
                obj.color, obj.icon, obj.name
            )
        return obj.name
    name_with_icon.short_description = 'Name'
    name_with_icon.admin_order_field = 'name'
    
    def expense_count(self, obj):
        """Display count of expenses."""
        count = obj.exp_count if hasattr(obj, 'exp_count') else obj.expenses.count()
        return count
    expense_count.short_description = 'Expenses'
    expense_count.admin_order_field = 'exp_count'
    
    def total_spent(self, obj):
        """Display total amount spent in category."""
        total = obj.exp_total if hasattr(obj, 'exp_total') else Decimal('0.00')
        return f"KES {total or 0:,.2f}"
    total_spent.short_description = 'Total Spent'
    total_spent.admin_order_field = 'exp_total'


@admin.register(ExpenseReceipt)
class ExpenseReceiptAdmin(admin.ModelAdmin):
    """Admin interface for expense receipts."""
    
    list_display = (
        'expense_link', 'file_name', 'file_type', 'file_size_display',
        'uploaded_by', 'uploaded_at'
    )
    
    list_filter = ('file_type', 'uploaded_at')
    
    search_fields = ('expense__title', 'file_name', 'description')
    
    readonly_fields = ('uploaded_by', 'uploaded_at', 'file_size', 'file_type')
    
    fieldsets = (
        ('Receipt Information', {
            'fields': ('expense', 'file', 'description')
        }),
        ('Metadata', {
            'fields': (
                'file_name', 'file_size', 'file_type',
                'uploaded_by', 'uploaded_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'uploaded_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('expense', 'uploaded_by')
    
    def expense_link(self, obj):
        """Display expense as clickable link."""
        url = reverse('admin:expenses_expense_change', args=[obj.expense.pk])
        return format_html('<a href="{}">{}</a>', url, obj.expense.title)
    expense_link.short_description = 'Expense'
    expense_link.admin_order_field = 'expense__title'
    
    def file_size_display(self, obj):
        """Display formatted file size."""
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'


@admin.register(ExpenseReport)
class ExpenseReportAdmin(admin.ModelAdmin):
    """Admin interface for expense reports."""
    
    list_display = (
        'report_number', 'title', 'status_badge', 'submitted_by',
        'start_date', 'end_date', 'total_amount', 'item_count'
    )
    
    list_filter = ('status', 'start_date', 'end_date', 'created_at')
    
    search_fields = ('report_number', 'title', 'submitted_by__username')
    
    readonly_fields = (
        'report_number', 'total_amount', 'submitted_by',
        'approved_by', 'approved_at', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_number', 'title', 'description')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('status', 'total_amount')
        }),
        ('Submission & Approval', {
            'fields': (
                'submitted_by', 'approved_by', 'approved_at'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'submitted_by', 'approved_by'
        ).annotate(
            items_count=Count('items')
        )
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'DRAFT': '#6c757d',
            'SUBMITTED': '#007bff',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'PAID': '#17a2b8',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def item_count(self, obj):
        """Display count of expenses in report."""
        return obj.items_count if hasattr(obj, 'items_count') else obj.items.count()
    item_count.short_description = 'Items'
    item_count.admin_order_field = 'items_count'


@admin.register(ExpenseTag)
class ExpenseTagAdmin(admin.ModelAdmin):
    """Admin interface for expense tags."""
    
    list_display = ('name', 'color_display', 'usage_count', 'created_at')
    
    search_fields = ('name',)
    
    readonly_fields = ('created_at', 'usage_count')
    
    fieldsets = (
        ('Tag Information', {
            'fields': ('name', 'color')
        }),
        ('Statistics', {
            'fields': ('usage_count', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add usage count annotation."""
        qs = super().get_queryset(request)
        return qs.annotate(use_count=Count('expenses'))
    
    def color_display(self, obj):
        """Display color swatch."""
        return format_html(
            '<div style="width: 50px; height: 20px; background-color: {}; '
            'border: 1px solid #ccc; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'
    
    def usage_count(self, obj):
        """Display usage count."""
        return obj.use_count if hasattr(obj, 'use_count') else obj.expenses.count()
    usage_count.short_description = 'Usage'
    usage_count.admin_order_field = 'use_count'


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    """Admin interface for recurring expenses."""
    
    list_display = (
        'title', 'category', 'amount', 'frequency', 
        'start_date', 'end_date', 'is_active', 'last_generated'
    )
    
    list_filter = ('is_active', 'frequency', 'category', 'start_date')
    
    search_fields = ('title', 'description', 'vendor_name')
    
    readonly_fields = ('submitted_by', 'last_generated', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category')
        }),
        ('Financial Details', {
            'fields': ('amount', 'currency', 'payment_method', 'vendor_name')
        }),
        ('Recurrence', {
            'fields': ('frequency', 'start_date', 'end_date', 'is_active')
        }),
        ('Tracking', {
            'fields': ('submitted_by', 'last_generated', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'start_date'
    
    actions = ['activate_recurring', 'deactivate_recurring']
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('category', 'submitted_by')
    
    @admin.action(description='Activate selected recurring expenses')
    def activate_recurring(self, request, queryset):
        """Activate recurring expenses."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} recurring expense(s) activated.')
    
    @admin.action(description='Deactivate selected recurring expenses')
    def deactivate_recurring(self, request, queryset):
        """Deactivate recurring expenses."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} recurring expense(s) deactivated.')


@admin.register(ExpenseApprovalWorkflow)
class ExpenseApprovalWorkflowAdmin(admin.ModelAdmin):
    """Admin interface for approval workflow."""
    
    list_display = (
        'expense_link', 'approver', 'level', 'status_badge',
        'actioned_at', 'created_at'
    )
    
    list_filter = ('status', 'level', 'created_at', 'actioned_at')
    
    search_fields = ('expense__title', 'approver__username', 'comments')
    
    readonly_fields = ('created_at', 'actioned_at')
    
    fieldsets = (
        ('Approval Information', {
            'fields': ('expense', 'approver', 'level')
        }),
        ('Status', {
            'fields': ('status', 'comments')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'actioned_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('expense', 'approver')
    
    def expense_link(self, obj):
        """Display expense as clickable link."""
        url = reverse('admin:expenses_expense_change', args=[obj.expense.pk])
        return format_html('<a href="{}">{}</a>', url, obj.expense.title)
    expense_link.short_description = 'Expense'
    expense_link.admin_order_field = 'expense__title'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        color_map = {
            'PENDING': '#ffc107',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


# Register inline model (if needed)
@admin.register(ExpenseReportItem)
class ExpenseReportItemAdmin(admin.ModelAdmin):
    """Admin interface for report items."""
    
    list_display = ('report_link', 'expense_link', 'added_at')
    
    list_filter = ('added_at',)
    
    search_fields = ('report__report_number', 'expense__title')
    
    readonly_fields = ('added_at',)
    
    date_hierarchy = 'added_at'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('report', 'expense')
    
    def report_link(self, obj):
        """Display report as clickable link."""
        url = reverse('admin:expenses_expensereport_change', args=[obj.report.pk])
        return format_html('<a href="{}">{}</a>', url, obj.report.report_number)
    report_link.short_description = 'Report'
    
    def expense_link(self, obj):
        """Display expense as clickable link."""
        url = reverse('admin:expenses_expense_change', args=[obj.expense.pk])
        return format_html('<a href="{}">{}</a>', url, obj.expense.title)
    expense_link.short_description = 'Expense'