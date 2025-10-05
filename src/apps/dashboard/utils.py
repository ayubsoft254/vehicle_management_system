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
    Get overview data for main dashboard
    
    Returns:
        dict: Dashboard overview metrics
    """
    
    from apps.vehicles.models import Vehicle
    from apps.clients.models import Client
    from apps.payments.models import Payment
    from apps.auctions.models import Auction
    
    today = timezone.now().date()
    
    data = {
        'vehicles': {
            'total': Vehicle.objects.count(),
            'available': Vehicle.objects.filter(status='available').count(),
            'in_stock': Vehicle.objects.filter(status='in_stock').count(),
            'sold': Vehicle.objects.filter(status='sold').count(),
        },
        'clients': {
            'total': Client.objects.count(),
            'active': Client.objects.filter(is_active=True).count(),
            'new_today': Client.objects.filter(date_registered__date=today).count(),
        },
        'payments': {
            'total_today': Payment.objects.filter(
                payment_date=today,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'count_today': Payment.objects.filter(payment_date=today).count(),
            'pending': Payment.objects.filter(status='pending').count(),
        },
        'auctions': {
            'active': Auction.objects.filter(status='active').count(),
            'scheduled': Auction.objects.filter(status='scheduled').count(),
            'completed_today': Auction.objects.filter(
                status='completed',
                completed_at__date=today
            ).count(),
        },
    }
    
    return data


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
        payment_date__lte=date_to,
        status='completed'
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
    
    cutoff = timezone.now() - timedelta(days=days)
    
    # Vehicles sold
    sold_vehicles = Vehicle.objects.filter(
        status='sold',
        updated_at__gte=cutoff
    )
    
    # Revenue
    revenue = Payment.objects.filter(
        payment_date__gte=cutoff.date(),
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    data = {
        'vehicles_sold': sold_vehicles.count(),
        'total_revenue': float(revenue),
        'average_sale_price': float(sold_vehicles.aggregate(avg=Avg('price'))['avg'] or 0),
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
            payment_date=current,
            status='completed'
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
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    trend = []
    current = start_date
    
    while current <= end_date:
        daily_sales = Vehicle.objects.filter(
            status='sold',
            updated_at__date=current
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