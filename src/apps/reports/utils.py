"""
Reports App - Utility Functions
"""

from django.db.models import Count, Sum, Avg, Max, Min, Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, datetime
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


# ============================================================================
# DATE RANGE UTILITIES
# ============================================================================

def get_date_range(date_range_type, custom_from=None, custom_to=None):
    """
    Get date range tuple based on type
    
    Args:
        date_range_type: String identifier for range type
        custom_from: Custom from date (for custom range)
        custom_to: Custom to date (for custom range)
    
    Returns:
        tuple: (from_date, to_date)
    """
    
    today = timezone.now().date()
    
    if date_range_type == 'custom':
        return custom_from, custom_to
    elif date_range_type == 'today':
        return today, today
    elif date_range_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif date_range_type == 'last_7_days':
        return today - timedelta(days=7), today
    elif date_range_type == 'last_30_days':
        return today - timedelta(days=30), today
    elif date_range_type == 'last_quarter':
        return today - timedelta(days=90), today
    elif date_range_type == 'last_year':
        return today - timedelta(days=365), today
    elif date_range_type == 'month_to_date':
        return today.replace(day=1), today
    elif date_range_type == 'year_to_date':
        return today.replace(month=1, day=1), today
    elif date_range_type == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif date_range_type == 'this_month':
        return today.replace(day=1), today
    elif date_range_type == 'this_year':
        return today.replace(month=1, day=1), today
    
    # Default to last 30 days
    return today - timedelta(days=30), today


def format_date_range(from_date, to_date):
    """Format date range for display"""
    if from_date == to_date:
        return from_date.strftime('%B %d, %Y')
    return f"{from_date.strftime('%B %d, %Y')} - {to_date.strftime('%B %d, %Y')}"


# ============================================================================
# DATA AGGREGATION UTILITIES
# ============================================================================

def aggregate_queryset(queryset, aggregations):
    """
    Apply aggregations to queryset
    
    Args:
        queryset: Django QuerySet
        aggregations: List of aggregation configs
            [{'field': 'amount', 'function': 'sum', 'alias': 'total_amount'}]
    
    Returns:
        dict: Aggregation results
    """
    
    agg_map = {
        'count': Count,
        'sum': Sum,
        'avg': Avg,
        'max': Max,
        'min': Min,
    }
    
    agg_dict = {}
    
    for agg in aggregations:
        field = agg.get('field')
        function = agg.get('function', 'count')
        alias = agg.get('alias', f"{field}_{function}")
        
        if function in agg_map:
            if function == 'count':
                agg_dict[alias] = agg_map[function](field)
            else:
                agg_dict[alias] = agg_map[function](field)
    
    return queryset.aggregate(**agg_dict)


def group_queryset(queryset, group_by, aggregations=None):
    """
    Group queryset by fields with aggregations
    
    Args:
        queryset: Django QuerySet
        group_by: List of fields to group by
        aggregations: List of aggregation configs
    
    Returns:
        QuerySet: Grouped and aggregated queryset
    """
    
    if isinstance(group_by, str):
        group_by = [group_by]
    
    result = queryset.values(*group_by)
    
    if aggregations:
        agg_dict = {}
        agg_map = {
            'count': Count,
            'sum': Sum,
            'avg': Avg,
            'max': Max,
            'min': Min,
        }
        
        for agg in aggregations:
            field = agg.get('field')
            function = agg.get('function', 'count')
            alias = agg.get('alias', f"{field}_{function}")
            
            if function in agg_map:
                if function == 'count':
                    agg_dict[alias] = agg_map[function](field)
                else:
                    agg_dict[alias] = agg_map[function](field)
        
        result = result.annotate(**agg_dict)
    
    return result


# ============================================================================
# REPORT DATA GENERATORS
# ============================================================================

def generate_financial_report_data(date_from, date_to):
    """Generate financial report data"""
    from apps.payments.models import Payment
    from apps.expenses.models import Expense
    
    payments = Payment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        status='completed'
    )
    
    expenses = Expense.objects.filter(
        expense_date__gte=date_from,
        expense_date__lte=date_to,
        status='approved'
    )
    
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_profit = total_revenue - total_expenses
    
    data = {
        'summary': {
            'total_revenue': float(total_revenue),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
            'profit_margin': float((net_profit / total_revenue * 100) if total_revenue > 0 else 0),
            'payment_count': payments.count(),
            'expense_count': expenses.count(),
        },
        'payments': list(payments.values(
            'id', 'amount', 'payment_date', 'payment_method', 'client__name'
        )),
        'expenses': list(expenses.values(
            'id', 'amount', 'expense_date', 'category', 'description'
        )),
        'revenue_by_method': list(
            payments.values('payment_method').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
        ),
        'expenses_by_category': list(
            expenses.values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
        ),
    }
    
    return data


def generate_vehicle_report_data(date_from, date_to):
    """Generate vehicle report data"""
    from apps.vehicles.models import Vehicle
    
    vehicles = Vehicle.objects.filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    )
    
    data = {
        'summary': {
            'total_vehicles': vehicles.count(),
            'by_status': dict(vehicles.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')),
            'by_make': dict(vehicles.values('make').annotate(
                count=Count('id')
            ).order_by('-count')[:10].values_list('make', 'count')),
            'average_price': float(vehicles.aggregate(avg=Avg('price'))['avg'] or 0),
            'total_value': float(vehicles.aggregate(sum=Sum('price'))['sum'] or 0),
        },
        'vehicles': list(vehicles.values(
            'id', 'vin', 'make', 'model', 'year', 'status', 'price'
        )),
    }
    
    return data


def generate_client_report_data(date_from, date_to):
    """Generate client report data"""
    from apps.clients.models import Client
    from apps.payments.models import Payment
    
    clients = Client.objects.filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    )
    
    # Get payment statistics for clients
    client_payments = Payment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        status='completed'
    ).values('client').annotate(
        total_paid=Sum('amount'),
        payment_count=Count('id')
    )
    
    data = {
        'summary': {
            'total_clients': clients.count(),
            'new_clients': clients.count(),
            'active_clients': Client.objects.filter(is_active=True).count(),
        },
        'clients': list(clients.values(
            'id', 'name', 'email', 'phone', 'created_at'
        )),
        'top_clients': list(client_payments.order_by('-total_paid')[:10]),
    }
    
    return data


def generate_auction_report_data(date_from, date_to):
    """Generate auction report data"""
    from apps.auctions.models import Auction, Bid
    
    auctions = Auction.objects.filter(
        start_date__gte=date_from,
        start_date__lte=date_to
    )
    
    data = {
        'summary': {
            'total_auctions': auctions.count(),
            'completed_auctions': auctions.filter(status='completed').count(),
            'active_auctions': auctions.filter(status='active').count(),
            'total_bids': Bid.objects.filter(auction__in=auctions).count(),
            'average_bids_per_auction': auctions.aggregate(avg=Avg('total_bids'))['avg'] or 0,
            'total_revenue': float(auctions.filter(
                status='completed'
            ).aggregate(sum=Sum('winning_bid_amount'))['sum'] or 0),
        },
        'auctions': list(auctions.values(
            'id', 'auction_number', 'title', 'status', 'current_bid',
            'total_bids', 'start_date', 'end_date'
        )),
        'top_auctions': list(
            auctions.filter(status='completed').order_by('-winning_bid_amount')[:10].values(
                'auction_number', 'title', 'winning_bid_amount', 'total_bids'
            )
        ),
    }
    
    return data


def generate_payment_report_data(date_from, date_to):
    """Generate payment report data"""
    from apps.payments.models import Payment
    
    payments = Payment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to
    )
    
    data = {
        'summary': {
            'total_payments': payments.count(),
            'completed_payments': payments.filter(status='completed').count(),
            'pending_payments': payments.filter(status='pending').count(),
            'failed_payments': payments.filter(status='failed').count(),
            'total_amount': float(payments.filter(
                status='completed'
            ).aggregate(sum=Sum('amount'))['sum'] or 0),
            'average_payment': float(payments.filter(
                status='completed'
            ).aggregate(avg=Avg('amount'))['avg'] or 0),
        },
        'payments': list(payments.values(
            'id', 'amount', 'payment_date', 'payment_method',
            'status', 'client__name'
        )),
        'by_method': list(
            payments.filter(status='completed').values('payment_method').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
        ),
        'by_status': list(
            payments.values('status').annotate(count=Count('id'))
        ),
    }
    
    return data


def generate_sales_report_data(date_from, date_to):
    """Generate sales report data"""
    from apps.vehicles.models import Vehicle
    from apps.payments.models import Payment
    
    # Vehicles sold in period
    sold_vehicles = Vehicle.objects.filter(
        status='sold',
        updated_at__gte=date_from,
        updated_at__lte=date_to
    )
    
    # Payments received
    payments = Payment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        status='completed'
    )
    
    data = {
        'summary': {
            'vehicles_sold': sold_vehicles.count(),
            'total_revenue': float(payments.aggregate(sum=Sum('amount'))['sum'] or 0),
            'average_sale_price': float(sold_vehicles.aggregate(avg=Avg('price'))['avg'] or 0),
        },
        'sales': list(sold_vehicles.values(
            'id', 'vin', 'make', 'model', 'year', 'price', 'updated_at'
        )),
        'revenue_trend': generate_revenue_trend(payments, date_from, date_to),
    }
    
    return data


# ============================================================================
# WIDGET DATA GENERATORS
# ============================================================================

def generate_widget_data(widget):
    """
    Generate data for a report widget
    
    Args:
        widget: ReportWidget instance
    
    Returns:
        dict: Widget data
    """
    
    data = {
        'id': str(widget.id),
        'name': widget.name,
        'widget_type': widget.widget_type,
        'chart_type': widget.chart_type,
        'data': None,
    }
    
    try:
        # Parse query config
        query_config = widget.query_config or {}
        
        # Get data based on data source
        if widget.data_source == 'Vehicle':
            from apps.vehicles.models import Vehicle
            queryset = Vehicle.objects.all()
        elif widget.data_source == 'Payment':
            from apps.payments.models import Payment
            queryset = Payment.objects.all()
        elif widget.data_source == 'Client':
            from apps.clients.models import Client
            queryset = Client.objects.all()
        elif widget.data_source == 'Auction':
            from apps.auctions.models import Auction
            queryset = Auction.objects.all()
        else:
            data['data'] = {'error': 'Unknown data source'}
            return data
        
        # Apply filters from query config
        filters = query_config.get('filters', {})
        if filters:
            queryset = queryset.filter(**filters)
        
        # Generate data based on widget type
        if widget.widget_type == 'metric':
            data['data'] = generate_metric_data(queryset, query_config)
        elif widget.widget_type in ['chart', 'gauge', 'trend']:
            data['data'] = generate_chart_data(queryset, query_config, widget.chart_type)
        elif widget.widget_type == 'table':
            data['data'] = generate_table_data(queryset, query_config)
        elif widget.widget_type == 'list':
            data['data'] = generate_list_data(queryset, query_config)
        
    except Exception as e:
        logger.error(f"Error generating widget data: {e}")
        data['data'] = {'error': str(e)}
    
    return data


def generate_metric_data(queryset, config):
    """Generate metric card data"""
    
    aggregation = config.get('aggregation', 'count')
    field = config.get('field')
    
    if aggregation == 'count':
        value = queryset.count()
    elif aggregation == 'sum' and field:
        value = queryset.aggregate(total=Sum(field))['total'] or 0
    elif aggregation == 'avg' and field:
        value = queryset.aggregate(avg=Avg(field))['avg'] or 0
    else:
        value = queryset.count()
    
    return {
        'value': float(value) if isinstance(value, Decimal) else value,
        'label': config.get('label', 'Total'),
    }


def generate_chart_data(queryset, config, chart_type):
    """Generate chart data"""
    
    group_by = config.get('group_by')
    aggregation = config.get('aggregation', 'count')
    field = config.get('field')
    
    if not group_by:
        return {'labels': [], 'values': []}
    
    if aggregation == 'count':
        data = queryset.values(group_by).annotate(value=Count('id'))
    elif aggregation == 'sum' and field:
        data = queryset.values(group_by).annotate(value=Sum(field))
    elif aggregation == 'avg' and field:
        data = queryset.values(group_by).annotate(value=Avg(field))
    else:
        data = queryset.values(group_by).annotate(value=Count('id'))
    
    labels = [item[group_by] for item in data]
    values = [float(item['value']) if isinstance(item['value'], Decimal) else item['value'] for item in data]
    
    return {
        'labels': labels,
        'values': values,
        'chart_type': chart_type,
    }


def generate_table_data(queryset, config):
    """Generate table data"""
    
    fields = config.get('fields', [])
    limit = config.get('limit', 10)
    
    if not fields:
        return {'columns': [], 'rows': []}
    
    data = list(queryset.values(*fields)[:limit])
    
    return {
        'columns': fields,
        'rows': data,
    }


def generate_list_data(queryset, config):
    """Generate list data"""
    
    fields = config.get('fields', ['id'])
    limit = config.get('limit', 10)
    
    items = list(queryset.values(*fields)[:limit])
    
    return {'items': items}


# ============================================================================
# TREND ANALYSIS
# ============================================================================

def generate_revenue_trend(queryset, date_from, date_to, interval='day'):
    """
    Generate revenue trend data
    
    Args:
        queryset: Payment QuerySet
        date_from: Start date
        date_to: End date
        interval: 'day', 'week', or 'month'
    
    Returns:
        list: Trend data points
    """
    
    trend = []
    
    if interval == 'day':
        current = date_from
        while current <= date_to:
            daily_revenue = queryset.filter(
                payment_date=current
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            trend.append({
                'date': current.isoformat(),
                'value': float(daily_revenue)
            })
            current += timedelta(days=1)
    
    elif interval == 'week':
        current = date_from
        while current <= date_to:
            week_end = min(current + timedelta(days=6), date_to)
            weekly_revenue = queryset.filter(
                payment_date__gte=current,
                payment_date__lte=week_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            trend.append({
                'date': current.isoformat(),
                'value': float(weekly_revenue)
            })
            current = week_end + timedelta(days=1)
    
    elif interval == 'month':
        current = date_from.replace(day=1)
        while current <= date_to:
            # Get last day of month
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1)
            else:
                next_month = current.replace(month=current.month + 1)
            month_end = next_month - timedelta(days=1)
            
            monthly_revenue = queryset.filter(
                payment_date__gte=current,
                payment_date__lte=month_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            trend.append({
                'date': current.isoformat(),
                'value': float(monthly_revenue)
            })
            current = next_month
    
    return trend


# ============================================================================
# REPORT STATISTICS
# ============================================================================

def calculate_report_statistics(report):
    """Calculate statistics for a report"""
    
    executions = report.executions.all()
    
    stats = {
        'total_executions': executions.count(),
        'successful': executions.filter(status='completed').count(),
        'failed': executions.filter(status='failed').count(),
        'average_execution_time': 0,
        'success_rate': 0,
        'last_execution': None,
    }
    
    # Calculate averages
    if stats['total_executions'] > 0:
        stats['success_rate'] = (stats['successful'] / stats['total_executions']) * 100
        
        avg_time = executions.filter(status='completed').aggregate(
            avg=Avg('execution_time')
        )['avg']
        stats['average_execution_time'] = float(avg_time) if avg_time else 0
    
    # Get last execution
    last = executions.order_by('-created_at').first()
    if last:
        stats['last_execution'] = {
            'id': str(last.id),
            'status': last.status,
            'created_at': last.created_at.isoformat(),
            'execution_time': float(last.execution_time) if last.execution_time else None,
        }
    
    return stats


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_currency(amount):
    """Format amount as currency"""
    return f"${float(amount):,.2f}"


def format_percentage(value):
    """Format value as percentage"""
    return f"{float(value):.2f}%"


def sanitize_filename(filename):
    """Sanitize filename for safe file system use"""
    import re
    # Remove invalid characters
    filename = re.sub(r'[^\w\s-]', '', filename)
    # Replace spaces with underscores
    filename = re.sub(r'\s+', '_', filename)
    return filename