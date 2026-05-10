"""
Dashboard App - Utility Functions
Dashboard data aggregation and helper functions
"""

from django.db.models import Count, Sum, Avg, Max, Min, Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, datetime
from decimal import Decimal
import json
import logging

from .models import MetricCache, DashboardActivity

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================================
# DASHBOARD DATA AGGREGATION
# ============================================================================

def get_dashboard_overview_data(user=None):
    """
    Get overview data for main dashboard — expanded with financial analytics,
    defaulters, most-sold makes, outstanding balances and recent sales.

    Returns:
        dict: Dashboard overview metrics
    """

    from apps.vehicles.models import Vehicle
    from apps.clients.models import Client, ClientVehicle
    from apps.payments.models import Payment, PaymentSchedule
    from apps.auctions.models import Auction
    from utils.constants import VehicleStatus

    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)

    # ── Vehicle statistics ────────────────────────────────────────────
    total_vehicles       = Vehicle.objects.count()
    available_vehicles   = Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).count()
    reserved_vehicles    = Vehicle.objects.filter(status=VehicleStatus.RESERVED).count()
    sold_vehicles        = Vehicle.objects.filter(status=VehicleStatus.SOLD).count()
    repossessed_vehicles = Vehicle.objects.filter(status=VehicleStatus.REPOSSESSED).count()
    maintenance_vehicles = Vehicle.objects.filter(status=VehicleStatus.MAINTENANCE).count()

    # ── Client statistics ─────────────────────────────────────────────
    total_clients     = Client.objects.count()
    active_clients    = Client.objects.filter(is_active=True).count()
    new_clients_today = Client.objects.filter(date_registered__date=today).count()

    # ── Payment statistics ────────────────────────────────────────────
    payments_today        = Payment.objects.filter(payment_date=today)
    total_payments_today  = payments_today.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    payments_count_today  = payments_today.count()

    monthly_revenue = Payment.objects.filter(
        payment_date__gte=first_day_of_month,
        payment_date__lte=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_revenue_all_time = Payment.objects.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    pending_payments = PaymentSchedule.objects.pending().count()

    # ── TOTAL MONEY OUTSIDE (outstanding balances) ────────────────────
    total_outstanding = ClientVehicle.objects.filter(
        is_paid_off=False
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    active_accounts = ClientVehicle.objects.filter(
        is_paid_off=False,
        payment_type='installment'
    ).count()

    # ── TOTAL SALES ───────────────────────────────────────────────────
    sold_cv = ClientVehicle.objects.select_related('vehicle', 'client')
    total_sales_revenue   = sold_cv.aggregate(total=Sum('purchase_price'))['total'] or Decimal('0.00')
    total_sales_count     = sold_cv.count()
    monthly_sales_count   = sold_cv.filter(purchase_date__gte=first_day_of_month).count()
    monthly_sales_revenue = sold_cv.filter(
        purchase_date__gte=first_day_of_month
    ).aggregate(total=Sum('purchase_price'))['total'] or Decimal('0.00')

    # ── PROFIT / LOSS ─────────────────────────────────────────────────
    sold_profit_qs = ClientVehicle.objects.select_related('vehicle')
    profit_data = sold_profit_qs.aggregate(
        total_sales=Sum('purchase_price'),
        total_purchase=Sum('vehicle__purchase_price'),
        total_duty=Sum('vehicle__duty_cost'),
        total_clearance=Sum('vehicle__clearance_cost'),
        total_commission_cost=Sum('vehicle__commission_cost'),
    )
    total_sales_value = profit_data['total_sales'] or Decimal('0.00')
    total_purchase = profit_data['total_purchase'] or Decimal('0.00')
    total_duty = profit_data['total_duty'] or Decimal('0.00')
    total_clearance = profit_data['total_clearance'] or Decimal('0.00')
    total_comm_cost = profit_data['total_commission_cost'] or Decimal('0.00')
    total_cost_base = total_purchase + total_duty + total_clearance + total_comm_cost
    total_profit_loss = total_sales_value - total_cost_base

    monthly_profit_data = sold_profit_qs.filter(
        purchase_date__gte=first_day_of_month
    ).aggregate(
        total_sales=Sum('purchase_price'),
        total_purchase=Sum('vehicle__purchase_price'),
        total_duty=Sum('vehicle__duty_cost'),
        total_clearance=Sum('vehicle__clearance_cost'),
        total_commission_cost=Sum('vehicle__commission_cost'),
    )
    m_sales = monthly_profit_data['total_sales'] or Decimal('0.00')
    m_purchase = monthly_profit_data['total_purchase'] or Decimal('0.00')
    m_duty = monthly_profit_data['total_duty'] or Decimal('0.00')
    m_clearance = monthly_profit_data['total_clearance'] or Decimal('0.00')
    m_comm = monthly_profit_data['total_commission_cost'] or Decimal('0.00')
    monthly_profit = m_sales - (m_purchase + m_duty + m_clearance + m_comm)

    # ── MOST SOLD CARS (by make) ──────────────────────────────────────
    most_sold_makes = list(
        ClientVehicle.objects.values('vehicle__make')
        .annotate(count=Count('id'), revenue=Sum('purchase_price'))
        .order_by('-count')[:5]
    )
    for item in most_sold_makes:
        item['make']    = item.pop('vehicle__make', '')
        item['revenue'] = float(item['revenue'] or 0)

    # ── MOST SOLD CARS (model breakdown) ──────────────────────────────
    most_sold_models = list(
        ClientVehicle.objects.values('vehicle__make', 'vehicle__model', 'vehicle__year')
        .annotate(count=Count('id'), revenue=Sum('purchase_price'))
        .order_by('-count', '-revenue')[:8]
    )
    for item in most_sold_models:
        year = item.get('vehicle__year')
        make = item.get('vehicle__make') or ''
        model = item.get('vehicle__model') or ''
        item['vehicle_name'] = f"{year} {make} {model}".strip()
        item['revenue'] = float(item.get('revenue') or 0)

    # ── DEFAULTERS LIST ───────────────────────────────────────────────
    try:
        overdue_schedules = PaymentSchedule.objects.filter(
            is_paid=False,
            due_date__lt=today,
        ).select_related(
            'client_vehicle__client', 'client_vehicle__vehicle'
        ).order_by('due_date')[:30]

        seen_clients = {}
        for sched in overdue_schedules:
            cv     = sched.client_vehicle
            client = cv.client
            cid    = client.pk
            days_od = (today - sched.due_date).days
            remaining_due = (sched.amount_due or Decimal('0.00')) - (sched.amount_paid or Decimal('0.00'))
            if remaining_due < 0:
                remaining_due = Decimal('0.00')
            if cid not in seen_clients:
                seen_clients[cid] = {
                    'client_id':         cid,
                    'client_name':       client.get_full_name(),
                    'phone':             client.phone_primary or '',
                    'vehicle':           str(cv.vehicle),
                    'client_vehicle_id': cv.pk,
                    'balance':           float(cv.balance),
                    'overdue_amount':    float(remaining_due),
                    'overdue_since':     sched.due_date.isoformat(),
                    'days_overdue':      days_od,
                }
            else:
                seen_clients[cid]['overdue_amount'] += float(remaining_due)
                if days_od > seen_clients[cid]['days_overdue']:
                    seen_clients[cid]['days_overdue'] = days_od

        defaulters = sorted(seen_clients.values(), key=lambda x: x['days_overdue'], reverse=True)[:10]
    except Exception:
        defaulters = []

    total_overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today,
    )
    overdue_total_amount = total_overdue_schedules.aggregate(
        total=Sum('amount_due')
    )['total'] or Decimal('0.00')
    overdue_total_paid_portion = total_overdue_schedules.aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')
    total_overdue_amount = overdue_total_amount - overdue_total_paid_portion
    if total_overdue_amount < 0:
        total_overdue_amount = Decimal('0.00')

    collection_rate = Decimal('0.00')
    if total_sales_revenue > 0:
        collection_rate = ((total_revenue_all_time / total_sales_revenue) * Decimal('100')).quantize(Decimal('0.01'))

    # ── RECENT SALES ──────────────────────────────────────────────────
    recent_sales = list(
        ClientVehicle.objects.select_related('client', 'vehicle')
        .order_by('-purchase_date')[:5]
        .values(
            'client__first_name', 'client__last_name',
            'vehicle__make', 'vehicle__model', 'vehicle__year',
            'purchase_price', 'deposit_paid', 'balance',
            'purchase_date', 'pk',
        )
    )
    for s in recent_sales:
        s['client_name']  = f"{s.pop('client__first_name','')} {s.pop('client__last_name','')}".strip()
        s['vehicle_name'] = f"{s.pop('vehicle__year','')} {s.pop('vehicle__make','')} {s.pop('vehicle__model','')}".strip()
        s['purchase_price'] = float(s['purchase_price'] or 0)
        s['deposit_paid']   = float(s['deposit_paid'] or 0)
        s['balance']        = float(s['balance'] or 0)

    # ── AUCTION statistics ────────────────────────────────────────────
    active_auctions          = Auction.objects.filter(status='active').count()
    scheduled_auctions       = Auction.objects.filter(status='scheduled').count()
    completed_auctions_today = Auction.objects.filter(status='completed', completed_at__date=today).count()

    return {
        'total_vehicles':  total_vehicles,
        'total_clients':   total_clients,
        'monthly_revenue': float(monthly_revenue),
        'pending_sales':   reserved_vehicles,

        'vehicles': {
            'total': total_vehicles, 'available': available_vehicles,
            'reserved': reserved_vehicles, 'sold': sold_vehicles,
            'repossessed': repossessed_vehicles, 'maintenance': maintenance_vehicles,
        },
        'clients': {
            'total': total_clients, 'active': active_clients, 'new_today': new_clients_today,
        },
        'payments': {
            'total_today': float(total_payments_today), 'count_today': payments_count_today,
            'pending': pending_payments, 'monthly_revenue': float(monthly_revenue),
            'all_time': float(total_revenue_all_time),
        },
        'outstanding': {
            'total': float(total_outstanding), 'active_accounts': active_accounts,
            'overdue_total': float(total_overdue_amount),
            'overdue_schedules': total_overdue_schedules.count(),
        },
        'sales': {
            'total_count': total_sales_count, 'total_revenue': float(total_sales_revenue),
            'monthly_count': monthly_sales_count, 'monthly_revenue': float(monthly_sales_revenue),
            'collection_rate_percent': float(collection_rate),
        },
        'profit': {
            'total': float(total_profit_loss), 'monthly': float(monthly_profit),
            'is_profitable': total_profit_loss >= 0,
            'monthly_is_profitable': monthly_profit >= 0,
        },
        'most_sold_makes': most_sold_makes,
        'most_sold_models': most_sold_models,
        'defaulters':      defaulters,
        'recent_sales':    recent_sales,
        'auctions': {
            'active': active_auctions, 'scheduled': scheduled_auctions,
            'completed_today': completed_auctions_today,
        },
        'today': today.isoformat(),
        'first_day_of_month': first_day_of_month.isoformat(),
    }


def get_financial_summary(date_from=None, date_to=None):
    """
    Get financial summary data
    
    Args:
        date_from: Start date (defaults to 30 days ago)
        date_to: End date (defaults to today)
    
    Returns:
        dict: Financial metrics
    """
    
    from apps.payments.models import Payment
    from apps.expenses.models import Expense
    
    if not date_from:
        date_from = timezone.now().date() - timedelta(days=30)
    if not date_to:
        date_to = timezone.now().date()
    
    # Revenue
    payments = Payment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to
    )
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Expenses
    expenses = Expense.objects.filter(
        expense_date__gte=date_from,
        expense_date__lte=date_to,
        status='approved'
    )
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Profit
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    data = {
        'total_revenue': float(total_revenue),
        'total_expenses': float(total_expenses),
        'net_profit': float(net_profit),
        'profit_margin': float(profit_margin),
        'payment_count': payments.count(),
        'expense_count': expenses.count(),
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
    }
    
    return data


def get_sales_metrics(days=30):
    """
    Get sales metrics for specified period
    
    Args:
        days: Number of days to analyze
    
    Returns:
        dict: Sales metrics
    """
    
    from apps.vehicles.models import Vehicle
    from apps.payments.models import Payment
    from utils.constants import VehicleStatus
    
    cutoff = timezone.now() - timedelta(days=days)
    
    # Vehicles sold
    sold_vehicles = Vehicle.objects.filter(
        status=VehicleStatus.SOLD,
        last_updated__gte=cutoff
    )
    
    # Revenue from payments
    revenue = Payment.objects.filter(
        payment_date__gte=cutoff.date()
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Average sale price from sold vehicles
    avg_price = sold_vehicles.aggregate(avg=Avg('selling_price'))['avg'] or Decimal('0.00')
    
    data = {
        'vehicles_sold': sold_vehicles.count(),
        'total_revenue': float(revenue),
        'average_sale_price': float(avg_price),
        'period_days': days,
    }
    
    return data


def get_auction_metrics():
    """
    Get auction performance metrics
    
    Returns:
        dict: Auction metrics
    """
    
    from apps.auctions.models import Auction, Bid
    
    active_auctions = Auction.objects.filter(status='active')
    
    data = {
        'active_auctions': active_auctions.count(),
        'total_bids_today': Bid.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'scheduled_auctions': Auction.objects.filter(status='scheduled').count(),
        'average_bids_per_auction': active_auctions.aggregate(
            avg=Avg('total_bids')
        )['avg'] or 0,
    }
    
    return data


# ============================================================================
# WIDGET DATA GENERATORS
# ============================================================================

def get_widget_data(widget):
    """
    Generate data for a specific widget
    
    Args:
        widget: Widget instance
    
    Returns:
        dict: Widget data
    """
    
    # Check cache first
    cache_key = f"widget_data_{widget.id}"
    cached_data = MetricCache.get_cached_value(cache_key)
    
    if cached_data:
        return cached_data
    
    # Generate data based on widget type
    data = None
    
    try:
        if widget.widget_type == 'metric':
            data = generate_metric_widget_data(widget)
        elif widget.widget_type == 'chart':
            data = generate_chart_widget_data(widget)
        elif widget.widget_type == 'table':
            data = generate_table_widget_data(widget)
        elif widget.widget_type == 'list':
            data = generate_list_widget_data(widget)
        elif widget.widget_type == 'activity':
            data = generate_activity_widget_data(widget)
        elif widget.widget_type == 'calendar':
            data = generate_calendar_widget_data(widget)
        elif widget.widget_type == 'gauge':
            data = generate_gauge_widget_data(widget)
        elif widget.widget_type == 'progress':
            data = generate_progress_widget_data(widget)
        else:
            data = {'error': 'Unknown widget type'}
        
        # Cache the data
        if data and widget.auto_refresh:
            MetricCache.set_cached_value(
                cache_key,
                widget.name,
                data,
                ttl_seconds=widget.refresh_interval
            )
    
    except Exception as e:
        logger.error(f"Error generating widget data: {e}")
        data = {'error': str(e)}
    
    return data


def generate_metric_widget_data(widget):
    """Generate data for metric card widget"""
    
    query_config = widget.query_config or {}
    model = get_model_from_source(widget.data_source)
    
    if not model:
        return {'value': 0, 'label': 'Error'}
    
    queryset = model.objects.all()
    
    # Apply filters
    filters = query_config.get('filters', {})
    if filters:
        queryset = queryset.filter(**filters)
    
    # Calculate metric
    aggregation = query_config.get('aggregation', 'count')
    field = query_config.get('field')
    
    if aggregation == 'count':
        value = queryset.count()
    elif aggregation == 'sum' and field:
        value = queryset.aggregate(total=Sum(field))['total'] or 0
    elif aggregation == 'avg' and field:
        value = queryset.aggregate(avg=Avg(field))['avg'] or 0
    elif aggregation == 'max' and field:
        value = queryset.aggregate(max=Max(field))['max'] or 0
    elif aggregation == 'min' and field:
        value = queryset.aggregate(min=Min(field))['min'] or 0
    else:
        value = queryset.count()
    
    # Format value
    if isinstance(value, Decimal):
        value = float(value)
    
    return {
        'value': value,
        'label': query_config.get('label', widget.name),
        'format': query_config.get('format', 'number'),
    }


def generate_chart_widget_data(widget):
    """Generate data for chart widget"""
    
    query_config = widget.query_config or {}
    model = get_model_from_source(widget.data_source)
    
    if not model:
        return {'labels': [], 'values': []}
    
    queryset = model.objects.all()
    
    # Apply filters
    filters = query_config.get('filters', {})
    if filters:
        queryset = queryset.filter(**filters)
    
    # Group and aggregate
    group_by = query_config.get('group_by')
    aggregation = query_config.get('aggregation', 'count')
    field = query_config.get('field')
    
    if group_by:
        if aggregation == 'count':
            data = queryset.values(group_by).annotate(value=Count('id'))
        elif aggregation == 'sum' and field:
            data = queryset.values(group_by).annotate(value=Sum(field))
        elif aggregation == 'avg' and field:
            data = queryset.values(group_by).annotate(value=Avg(field))
        else:
            data = queryset.values(group_by).annotate(value=Count('id'))
        
        labels = [str(item[group_by]) for item in data]
        values = [float(item['value']) if isinstance(item['value'], Decimal) else item['value'] for item in data]
    else:
        labels = []
        values = []
    
    return {
        'labels': labels,
        'values': values,
        'chart_type': widget.chart_type or 'bar',
    }


def generate_table_widget_data(widget):
    """Generate data for table widget"""
    
    query_config = widget.query_config or {}
    model = get_model_from_source(widget.data_source)
    
    if not model:
        return {'columns': [], 'rows': []}
    
    queryset = model.objects.all()
    
    # Apply filters
    filters = query_config.get('filters', {})
    if filters:
        queryset = queryset.filter(**filters)
    
    # Get fields
    fields = query_config.get('fields', [])
    if not fields:
        fields = ['id']
    
    # Limit results
    limit = query_config.get('limit', 10)
    
    rows = list(queryset.values(*fields)[:limit])
    
    return {
        'columns': fields,
        'rows': rows,
    }


def generate_list_widget_data(widget):
    """Generate data for list widget"""
    
    query_config = widget.query_config or {}
    model = get_model_from_source(widget.data_source)
    
    if not model:
        return {'items': []}
    
    queryset = model.objects.all()
    
    # Apply filters
    filters = query_config.get('filters', {})
    if filters:
        queryset = queryset.filter(**filters)
    
    # Get fields
    fields = query_config.get('fields', ['id'])
    limit = query_config.get('limit', 5)
    
    items = list(queryset.values(*fields)[:limit])
    
    return {'items': items}


def generate_activity_widget_data(widget):
    """Generate data for activity feed widget"""
    
    query_config = widget.query_config or {}
    limit = query_config.get('limit', 10)
    
    # Get recent activities from various sources
    activities = []
    
    # Could aggregate from audit logs, notifications, etc.
    # For now, return recent dashboard activities
    recent_activities = DashboardActivity.objects.select_related('user').order_by('-created_at')[:limit]
    
    for activity in recent_activities:
        activities.append({
            'type': activity.activity_type,
            'description': activity.description or activity.get_activity_type_display(),
            'user': activity.user.get_full_name() if activity.user else 'System',
            'timestamp': activity.created_at.isoformat(),
        })
    
    return {'activities': activities}


def generate_calendar_widget_data(widget):
    """Generate data for calendar widget"""
    
    # Return calendar events (could integrate with Google Calendar, etc.)
    return {
        'events': [],
        'month': timezone.now().month,
        'year': timezone.now().year,
    }


def generate_gauge_widget_data(widget):
    """Generate data for gauge widget"""
    
    query_config = widget.query_config or {}
    
    # Get current value (similar to metric)
    metric_data = generate_metric_widget_data(widget)
    value = metric_data.get('value', 0)
    
    # Get min/max for gauge
    min_value = query_config.get('min', 0)
    max_value = query_config.get('max', 100)
    
    return {
        'value': value,
        'min': min_value,
        'max': max_value,
        'label': metric_data.get('label'),
    }


def generate_progress_widget_data(widget):
    """Generate data for progress bar widget"""
    
    query_config = widget.query_config or {}
    
    # Get current and target values
    current = query_config.get('current', 0)
    target = query_config.get('target', 100)
    
    percentage = (current / target * 100) if target > 0 else 0
    
    return {
        'current': current,
        'target': target,
        'percentage': percentage,
        'label': query_config.get('label', widget.name),
    }


# ============================================================================
# TREND ANALYSIS
# ============================================================================

def get_revenue_trend(days=30):
    """Get revenue trend data"""
    
    from apps.payments.models import Payment
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    trend = []
    current = start_date
    
    while current <= end_date:
        daily_revenue = Payment.objects.filter(
            payment_date=current
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        trend.append({
            'date': current.isoformat(),
            'value': float(daily_revenue)
        })
        
        current += timedelta(days=1)
    
    return trend


def get_sales_trend(days=30):
    """Get sales trend data"""
    
    from apps.vehicles.models import Vehicle
    from utils.constants import VehicleStatus
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    trend = []
    current = start_date
    
    while current <= end_date:
        daily_sales = Vehicle.objects.filter(
            status=VehicleStatus.SOLD,
            last_updated__date=current
        ).count()
        
        trend.append({
            'date': current.isoformat(),
            'value': daily_sales
        })
        
        current += timedelta(days=1)
    
    return trend


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_model_from_source(data_source):
    """Get Django model from data source string"""
    
    models_map = {
        'Vehicle': 'apps.vehicles.models.Vehicle',
        'Client': 'apps.clients.models.Client',
        'Payment': 'apps.payments.models.Payment',
        'Expense': 'apps.expenses.models.Expense',
        'Auction': 'apps.auctions.models.Auction',
        'Bid': 'apps.auctions.models.Bid',
        'Repossession': 'apps.repossessions.models.Repossession',
        'Insurance': 'apps.insurance.models.Insurance',
    }
    
    model_path = models_map.get(data_source)
    if not model_path:
        return None
    
    try:
        module_path, class_name = model_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except (ImportError, AttributeError):
        return None


def log_dashboard_activity(dashboard, user, activity_type, description='', metadata=None):
    """Log dashboard activity"""
    
    DashboardActivity.objects.create(
        dashboard=dashboard,
        user=user,
        activity_type=activity_type,
        description=description,
        metadata=metadata or {}
    )


def format_currency(value):
    """Format value as currency"""
    return f"${float(value):,.2f}"


def format_number(value):
    """Format number with commas"""
    return f"{int(value):,}"


def format_percentage(value):
    """Format value as percentage"""
    return f"{float(value):.1f}%"


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def clear_dashboard_cache(dashboard):
    """Clear all cached data for a dashboard"""
    
    widget_ids = dashboard.widgets.values_list('id', flat=True)
    
    for widget_id in widget_ids:
        cache_key = f"widget_data_{widget_id}"
        MetricCache.objects.filter(metric_key=cache_key).delete()


def clear_expired_cache():
    """Clear all expired cache entries"""
    
    expired = MetricCache.objects.filter(expires_at__lt=timezone.now())
    count = expired.delete()[0]
    
    return count