"""
Dashboard App - Widget Definitions
Pre-configured widget templates for common dashboard widgets
"""

from django.utils import timezone
from datetime import timedelta


# ============================================================================
# WIDGET TEMPLATES
# ============================================================================

WIDGET_TEMPLATES = {
    # Financial Widgets
    'total_revenue': {
        'name': 'Total Revenue',
        'widget_type': 'metric',
        'data_source': 'Payment',
        'query_config': {
            'filters': {'status': 'completed'},
            'aggregation': 'sum',
            'field': 'amount',
            'label': 'Total Revenue',
            'format': 'currency',
        },
        'size': 'small',
        'order': 1,
    },
    
    'revenue_today': {
        'name': 'Revenue Today',
        'widget_type': 'metric',
        'data_source': 'Payment',
        'query_config': {
            'filters': {
                'status': 'completed',
                'payment_date': timezone.now().date(),
            },
            'aggregation': 'sum',
            'field': 'amount',
            'label': 'Today\'s Revenue',
            'format': 'currency',
        },
        'size': 'small',
        'order': 2,
    },
    
    'total_expenses': {
        'name': 'Total Expenses',
        'widget_type': 'metric',
        'data_source': 'Expense',
        'query_config': {
            'filters': {'status': 'approved'},
            'aggregation': 'sum',
            'field': 'amount',
            'label': 'Total Expenses',
            'format': 'currency',
        },
        'size': 'small',
        'order': 3,
    },
    
    'revenue_chart': {
        'name': 'Revenue by Method',
        'widget_type': 'chart',
        'chart_type': 'pie',
        'data_source': 'Payment',
        'query_config': {
            'filters': {'status': 'completed'},
            'group_by': 'payment_method',
            'aggregation': 'sum',
            'field': 'amount',
        },
        'size': 'medium',
        'order': 10,
    },
    
    # Vehicle Widgets
    'total_vehicles': {
        'name': 'Total Vehicles',
        'widget_type': 'metric',
        'data_source': 'Vehicle',
        'query_config': {
            'aggregation': 'count',
            'label': 'Total Vehicles',
            'format': 'number',
        },
        'size': 'small',
        'order': 4,
    },
    
    'available_vehicles': {
        'name': 'Available Vehicles',
        'widget_type': 'metric',
        'data_source': 'Vehicle',
        'query_config': {
            'filters': {'status': 'available'},
            'aggregation': 'count',
            'label': 'Available',
            'format': 'number',
        },
        'size': 'small',
        'order': 5,
    },
    
    'vehicles_by_status': {
        'name': 'Vehicles by Status',
        'widget_type': 'chart',
        'chart_type': 'doughnut',
        'data_source': 'Vehicle',
        'query_config': {
            'group_by': 'status',
            'aggregation': 'count',
        },
        'size': 'medium',
        'order': 11,
    },
    
    'vehicles_by_make': {
        'name': 'Vehicles by Make',
        'widget_type': 'chart',
        'chart_type': 'bar',
        'data_source': 'Vehicle',
        'query_config': {
            'group_by': 'make',
            'aggregation': 'count',
        },
        'size': 'large',
        'order': 12,
    },
    
    'recent_vehicles': {
        'name': 'Recent Vehicles',
        'widget_type': 'table',
        'data_source': 'Vehicle',
        'query_config': {
            'fields': ['vin', 'make', 'model', 'year', 'status', 'price'],
            'limit': 10,
        },
        'size': 'large',
        'order': 20,
    },
    
    # Client Widgets
    'total_clients': {
        'name': 'Total Clients',
        'widget_type': 'metric',
        'data_source': 'Client',
        'query_config': {
            'aggregation': 'count',
            'label': 'Total Clients',
            'format': 'number',
        },
        'size': 'small',
        'order': 6,
    },
    
    'active_clients': {
        'name': 'Active Clients',
        'widget_type': 'metric',
        'data_source': 'Client',
        'query_config': {
            'filters': {'is_active': True},
            'aggregation': 'count',
            'label': 'Active Clients',
            'format': 'number',
        },
        'size': 'small',
        'order': 7,
    },
    
    'recent_clients': {
        'name': 'Recent Clients',
        'widget_type': 'list',
        'data_source': 'Client',
        'query_config': {
            'fields': ['name', 'email', 'phone', 'created_at'],
            'limit': 5,
        },
        'size': 'medium',
        'order': 13,
    },
    
    # Auction Widgets
    'active_auctions': {
        'name': 'Active Auctions',
        'widget_type': 'metric',
        'data_source': 'Auction',
        'query_config': {
            'filters': {'status': 'active'},
            'aggregation': 'count',
            'label': 'Active Auctions',
            'format': 'number',
        },
        'size': 'small',
        'order': 8,
    },
    
    'total_bids_today': {
        'name': 'Bids Today',
        'widget_type': 'metric',
        'data_source': 'Bid',
        'query_config': {
            'filters': {'created_at__date': timezone.now().date()},
            'aggregation': 'count',
            'label': 'Bids Today',
            'format': 'number',
        },
        'size': 'small',
        'order': 9,
    },
    
    'auction_performance': {
        'name': 'Auction Performance',
        'widget_type': 'chart',
        'chart_type': 'line',
        'data_source': 'Auction',
        'query_config': {
            'group_by': 'status',
            'aggregation': 'count',
        },
        'size': 'large',
        'order': 14,
    },
    
    'recent_auctions': {
        'name': 'Recent Auctions',
        'widget_type': 'table',
        'data_source': 'Auction',
        'query_config': {
            'fields': ['auction_number', 'title', 'status', 'current_bid', 'start_date'],
            'limit': 8,
        },
        'size': 'large',
        'order': 21,
    },
    
    # Activity Widgets
    'activity_feed': {
        'name': 'Recent Activity',
        'widget_type': 'activity',
        'data_source': 'DashboardActivity',
        'query_config': {
            'limit': 10,
        },
        'size': 'medium',
        'order': 15,
    },
    
    # Progress Widgets
    'sales_target': {
        'name': 'Monthly Sales Target',
        'widget_type': 'progress',
        'data_source': 'Vehicle',
        'query_config': {
            'current': 0,  # Will be calculated dynamically
            'target': 50,
            'label': 'Sales Target',
        },
        'size': 'medium',
        'order': 16,
    },
    
    'collection_rate': {
        'name': 'Collection Rate',
        'widget_type': 'gauge',
        'data_source': 'Payment',
        'query_config': {
            'min': 0,
            'max': 100,
            'label': 'Collection Rate',
        },
        'size': 'small',
        'order': 17,
    },
}


# ============================================================================
# DEFAULT DASHBOARD CONFIGURATIONS
# ============================================================================

DEFAULT_DASHBOARDS = {
    'executive': {
        'name': 'Executive Dashboard',
        'description': 'High-level overview for executives',
        'layout': 'grid',
        'widgets': [
            'total_revenue',
            'revenue_today',
            'total_expenses',
            'total_vehicles',
            'total_clients',
            'active_auctions',
            'revenue_chart',
            'vehicles_by_status',
            'auction_performance',
        ],
    },
    
    'sales': {
        'name': 'Sales Dashboard',
        'description': 'Sales team performance tracking',
        'layout': 'grid',
        'widgets': [
            'available_vehicles',
            'total_clients',
            'revenue_today',
            'sales_target',
            'vehicles_by_status',
            'recent_vehicles',
            'recent_clients',
        ],
    },
    
    'finance': {
        'name': 'Finance Dashboard',
        'description': 'Financial metrics and reporting',
        'layout': 'grid',
        'widgets': [
            'total_revenue',
            'total_expenses',
            'revenue_today',
            'collection_rate',
            'revenue_chart',
            'auction_performance',
        ],
    },
    
    'operations': {
        'name': 'Operations Dashboard',
        'description': 'Day-to-day operations overview',
        'layout': 'grid',
        'widgets': [
            'total_vehicles',
            'available_vehicles',
            'active_auctions',
            'total_bids_today',
            'vehicles_by_make',
            'recent_vehicles',
            'recent_auctions',
            'activity_feed',
        ],
    },
}


# ============================================================================
# WIDGET HELPER FUNCTIONS
# ============================================================================

def get_widget_template(template_name):
    """
    Get widget template by name
    
    Args:
        template_name: Name of the widget template
    
    Returns:
        dict: Widget configuration
    """
    return WIDGET_TEMPLATES.get(template_name)


def get_all_widget_templates():
    """Get all available widget templates"""
    return WIDGET_TEMPLATES


def get_widget_templates_by_type(widget_type):
    """
    Get widget templates by type
    
    Args:
        widget_type: Widget type (metric, chart, table, etc.)
    
    Returns:
        dict: Filtered widget templates
    """
    return {
        name: config
        for name, config in WIDGET_TEMPLATES.items()
        if config.get('widget_type') == widget_type
    }


def create_widget_from_template(dashboard, template_name):
    """
    Create a widget from a template
    
    Args:
        dashboard: Dashboard instance
        template_name: Name of the widget template
    
    Returns:
        Widget: Created widget instance
    """
    from .models import Widget
    
    template = get_widget_template(template_name)
    if not template:
        raise ValueError(f"Widget template '{template_name}' not found")
    
    # Create widget
    widget = Widget.objects.create(
        dashboard=dashboard,
        name=template['name'],
        widget_type=template['widget_type'],
        chart_type=template.get('chart_type', ''),
        data_source=template['data_source'],
        query_config=template['query_config'],
        size=template.get('size', 'medium'),
        order=template.get('order', 0),
    )
    
    return widget


def create_dashboard_from_template(user, dashboard_type):
    """
    Create a complete dashboard from a template
    
    Args:
        user: User instance
        dashboard_type: Type of dashboard (executive, sales, finance, operations)
    
    Returns:
        Dashboard: Created dashboard instance
    """
    from .models import Dashboard
    
    template = DEFAULT_DASHBOARDS.get(dashboard_type)
    if not template:
        raise ValueError(f"Dashboard template '{dashboard_type}' not found")
    
    # Create dashboard
    dashboard = Dashboard.objects.create(
        created_by=user,
        name=template['name'],
        description=template['description'],
        layout=template['layout'],
    )
    
    # Create widgets
    for widget_name in template['widgets']:
        create_widget_from_template(dashboard, widget_name)
    
    return dashboard


def get_available_data_sources():
    """Get list of available data sources for widgets"""
    return [
        {'value': 'Vehicle', 'label': 'Vehicles'},
        {'value': 'Client', 'label': 'Clients'},
        {'value': 'Payment', 'label': 'Payments'},
        {'value': 'Expense', 'label': 'Expenses'},
        {'value': 'Auction', 'label': 'Auctions'},
        {'value': 'Bid', 'label': 'Bids'},
        {'value': 'Repossession', 'label': 'Repossessions'},
        {'value': 'Insurance', 'label': 'Insurance'},
    ]


def get_widget_icon(widget_type):
    """
    Get icon name for widget type
    
    Args:
        widget_type: Widget type
    
    Returns:
        str: Icon name
    """
    icons = {
        'metric': 'trending-up',
        'chart': 'bar-chart',
        'table': 'table',
        'list': 'list',
        'calendar': 'calendar',
        'activity': 'activity',
        'quick_actions': 'zap',
        'notification': 'bell',
        'gauge': 'gauge',
        'progress': 'trending-up',
        'map': 'map',
    }
    return icons.get(widget_type, 'square')


def get_chart_colors():
    """Get default color palette for charts"""
    return [
        '#3498db',  # Blue
        '#2ecc71',  # Green
        '#f39c12',  # Orange
        '#e74c3c',  # Red
        '#9b59b6',  # Purple
        '#1abc9c',  # Teal
        '#34495e',  # Dark Gray
        '#95a5a6',  # Gray
        '#f1c40f',  # Yellow
        '#e67e22',  # Dark Orange
    ]


# ============================================================================
# WIDGET VALIDATION
# ============================================================================

def validate_widget_config(widget_config):
    """
    Validate widget configuration
    
    Args:
        widget_config: Widget configuration dict
    
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # Check required fields
    required_fields = ['name', 'widget_type', 'data_source']
    for field in required_fields:
        if not widget_config.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Validate widget type
    valid_types = [
        'metric', 'chart', 'table', 'list', 'calendar',
        'activity', 'quick_actions', 'notification', 'gauge', 'progress', 'map'
    ]
    if widget_config.get('widget_type') not in valid_types:
        errors.append(f"Invalid widget type: {widget_config.get('widget_type')}")
    
    # Validate chart type if widget is chart
    if widget_config.get('widget_type') == 'chart':
        valid_chart_types = ['line', 'bar', 'pie', 'doughnut', 'area', 'scatter', 'radar']
        if widget_config.get('chart_type') not in valid_chart_types:
            errors.append(f"Invalid chart type: {widget_config.get('chart_type')}")
    
    return len(errors) == 0, errors


# ============================================================================
# WIDGET EXPORT/IMPORT
# ============================================================================

def export_widget_config(widget):
    """
    Export widget configuration as dict
    
    Args:
        widget: Widget instance
    
    Returns:
        dict: Widget configuration
    """
    return {
        'name': widget.name,
        'description': widget.description,
        'widget_type': widget.widget_type,
        'chart_type': widget.chart_type,
        'data_source': widget.data_source,
        'query_config': widget.query_config,
        'position_x': widget.position_x,
        'position_y': widget.position_y,
        'width': widget.width,
        'height': widget.height,
        'size': widget.size,
        'order': widget.order,
        'show_title': widget.show_title,
        'show_border': widget.show_border,
        'title_color': widget.title_color,
        'background_color': widget.background_color,
        'auto_refresh': widget.auto_refresh,
        'refresh_interval': widget.refresh_interval,
        'custom_css': widget.custom_css,
        'custom_config': widget.custom_config,
    }


def import_widget_config(dashboard, widget_config):
    """
    Import widget from configuration
    
    Args:
        dashboard: Dashboard instance
        widget_config: Widget configuration dict
    
    Returns:
        Widget: Created widget instance
    """
    from .models import Widget
    
    is_valid, errors = validate_widget_config(widget_config)
    if not is_valid:
        raise ValueError(f"Invalid widget configuration: {errors}")
    
    widget = Widget.objects.create(
        dashboard=dashboard,
        **widget_config
    )
    
    return widget