"""
Dashboard App - Models
Handles dashboard configuration, widgets, and user preferences
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


# ============================================================================
# CUSTOM MANAGERS
# ============================================================================

class DashboardManager(models.Manager):
    """Custom manager for Dashboard model"""
    
    def default_dashboards(self):
        """Get default dashboards"""
        return self.filter(is_default=True, is_active=True)
    
    def for_user(self, user):
        """Get dashboards accessible by user"""
        return self.filter(
            models.Q(created_by=user) |
            models.Q(is_public=True) |
            models.Q(shared_with=user)
        ).distinct()


class WidgetManager(models.Manager):
    """Custom manager for Widget model"""
    
    def active(self):
        """Get active widgets"""
        return self.filter(is_active=True)
    
    def by_type(self, widget_type):
        """Get widgets by type"""
        return self.filter(widget_type=widget_type)


# ============================================================================
# DASHBOARD MODEL
# ============================================================================

class Dashboard(models.Model):
    """
    Main dashboard configuration
    """
    
    LAYOUT_CHOICES = [
        ('grid', 'Grid Layout'),
        ('masonry', 'Masonry Layout'),
        ('flex', 'Flexible Layout'),
        ('custom', 'Custom Layout'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Layout Configuration
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default='grid'
    )
    columns = models.IntegerField(
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="Number of columns in grid layout"
    )
    
    # Access Control
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_dashboards'
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Allow all users to view this dashboard"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Set as default dashboard for users"
    )
    shared_with = models.ManyToManyField(
        User,
        related_name='shared_dashboards',
        blank=True
    )
    
    # Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(
        default=300,
        help_text="Auto-refresh interval in seconds"
    )
    theme = models.CharField(
        max_length=20,
        default='light',
        choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = DashboardManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'is_active']),
            models.Index(fields=['is_public', 'is_active']),
            models.Index(fields=['is_default']),
        ]
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
    
    def __str__(self):
        return f"{self.name} - {self.created_by.username}"
    
    def can_user_access(self, user):
        """Check if user can access this dashboard"""
        if user.is_staff or user.is_superuser:
            return True
        if self.created_by == user:
            return True
        if self.is_public:
            return True
        if user in self.shared_with.all():
            return True
        return False


# ============================================================================
# WIDGET MODEL
# ============================================================================

class Widget(models.Model):
    """
    Dashboard widget configuration
    """
    
    WIDGET_TYPE_CHOICES = [
        ('metric', 'Metric Card'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('list', 'List'),
        ('calendar', 'Calendar'),
        ('activity', 'Activity Feed'),
        ('quick_actions', 'Quick Actions'),
        ('notification', 'Notifications'),
        ('gauge', 'Gauge'),
        ('progress', 'Progress Bar'),
        ('map', 'Map'),
        ('custom', 'Custom Widget'),
    ]
    
    CHART_TYPE_CHOICES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('radar', 'Radar Chart'),
    ]
    
    SIZE_CHOICES = [
        ('small', 'Small (3 cols)'),
        ('medium', 'Medium (6 cols)'),
        ('large', 'Large (9 cols)'),
        ('full', 'Full Width (12 cols)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widgets'
    )
    
    # Widget Configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPE_CHOICES,
        blank=True
    )
    
    # Data Source
    data_source = models.CharField(
        max_length=100,
        help_text="Model or data source name"
    )
    query_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Query configuration and filters"
    )
    
    # Layout
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    width = models.IntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    height = models.IntegerField(
        default=300,
        validators=[MinValueValidator(100)]
    )
    size = models.CharField(
        max_length=20,
        choices=SIZE_CHOICES,
        default='medium'
    )
    order = models.IntegerField(default=0)
    
    # Display Settings
    show_title = models.BooleanField(default=True)
    show_border = models.BooleanField(default=True)
    title_color = models.CharField(max_length=20, default='#333333')
    background_color = models.CharField(max_length=20, default='#ffffff')
    
    # Refresh Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(
        default=300,
        help_text="Refresh interval in seconds"
    )
    
    # Custom Styling
    custom_css = models.TextField(blank=True)
    custom_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional widget-specific configuration"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = WidgetManager()
    
    class Meta:
        ordering = ['dashboard', 'order', 'position_y', 'position_x']
        indexes = [
            models.Index(fields=['dashboard', 'is_active']),
            models.Index(fields=['widget_type']),
            models.Index(fields=['order']),
        ]
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
    
    def __str__(self):
        return f"{self.name} ({self.get_widget_type_display()})"


# ============================================================================
# USER DASHBOARD PREFERENCE MODEL
# ============================================================================

class UserDashboardPreference(models.Model):
    """
    User-specific dashboard preferences
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_preferences'
    )
    
    # Default Dashboard
    default_dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_users'
    )
    
    # Display Preferences
    theme = models.CharField(
        max_length=20,
        default='auto',
        choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')]
    )
    compact_mode = models.BooleanField(default=False)
    show_grid_lines = models.BooleanField(default=True)
    
    # Widget Preferences
    default_refresh_interval = models.IntegerField(default=300)
    enable_animations = models.BooleanField(default=True)
    
    # Notification Preferences
    show_notifications = models.BooleanField(default=True)
    show_quick_actions = models.BooleanField(default=True)
    show_activity_feed = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Dashboard Preference'
        verbose_name_plural = 'User Dashboard Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"


# ============================================================================
# DASHBOARD ACTIVITY MODEL
# ============================================================================

class DashboardActivity(models.Model):
    """
    Track dashboard activity and events
    """
    
    ACTIVITY_TYPE_CHOICES = [
        ('view', 'Dashboard Viewed'),
        ('widget_added', 'Widget Added'),
        ('widget_removed', 'Widget Removed'),
        ('widget_updated', 'Widget Updated'),
        ('layout_changed', 'Layout Changed'),
        ('shared', 'Dashboard Shared'),
        ('exported', 'Dashboard Exported'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dashboard_activities'
    )
    
    # Activity Details
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dashboard', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['activity_type', '-created_at']),
        ]
        verbose_name = 'Dashboard Activity'
        verbose_name_plural = 'Dashboard Activities'
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# ============================================================================
# QUICK ACTION MODEL
# ============================================================================

class QuickAction(models.Model):
    """
    Quick action buttons for dashboard
    """
    
    ICON_CHOICES = [
        ('plus', 'Plus'),
        ('edit', 'Edit'),
        ('trash', 'Trash'),
        ('eye', 'View'),
        ('download', 'Download'),
        ('upload', 'Upload'),
        ('refresh', 'Refresh'),
        ('settings', 'Settings'),
        ('user', 'User'),
        ('file', 'File'),
        ('search', 'Search'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Action Configuration
    action_type = models.CharField(
        max_length=50,
        help_text="Type of action (link, modal, api_call, etc.)"
    )
    action_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL or endpoint for the action"
    )
    action_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional action configuration"
    )
    
    # Display
    icon = models.CharField(max_length=50, choices=ICON_CHOICES, default='plus')
    color = models.CharField(max_length=20, default='#007bff')
    order = models.IntegerField(default=0)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    allowed_users = models.ManyToManyField(
        User,
        related_name='accessible_quick_actions',
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Quick Action'
        verbose_name_plural = 'Quick Actions'
    
    def __str__(self):
        return self.name
    
    def can_user_access(self, user):
        """Check if user can access this action"""
        if user.is_staff or user.is_superuser:
            return True
        if self.is_public:
            return True
        if user in self.allowed_users.all():
            return True
        return False


# ============================================================================
# DASHBOARD SNAPSHOT MODEL
# ============================================================================

class DashboardSnapshot(models.Model):
    """
    Saved dashboard snapshots for historical reference
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='snapshots'
    )
    
    # Snapshot Details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Complete dashboard configuration and data"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_snapshots'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dashboard', '-created_at']),
        ]
        verbose_name = 'Dashboard Snapshot'
        verbose_name_plural = 'Dashboard Snapshots'
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%Y-%m-%d')}"


# ============================================================================
# METRIC CACHE MODEL
# ============================================================================

class MetricCache(models.Model):
    """
    Cache for frequently accessed metrics
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metric Identification
    metric_key = models.CharField(max_length=255, unique=True, db_index=True)
    metric_name = models.CharField(max_length=255)
    
    # Cached Data
    value = models.JSONField(help_text="Cached metric value")
    
    # Cache Management
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['metric_key']),
            models.Index(fields=['expires_at']),
        ]
        verbose_name = 'Metric Cache'
        verbose_name_plural = 'Metric Caches'
    
    def __str__(self):
        return f"{self.metric_name} (expires: {self.expires_at})"
    
    @property
    def is_expired(self):
        """Check if cache has expired"""
        return timezone.now() > self.expires_at
    
    @classmethod
    def get_cached_value(cls, metric_key):
        """Get cached value if not expired"""
        try:
            cache = cls.objects.get(metric_key=metric_key)
            if not cache.is_expired:
                return cache.value
            else:
                cache.delete()
                return None
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def set_cached_value(cls, metric_key, metric_name, value, ttl_seconds=300):
        """Set cached value with TTL"""
        expires_at = timezone.now() + timezone.timedelta(seconds=ttl_seconds)
        
        cache, created = cls.objects.update_or_create(
            metric_key=metric_key,
            defaults={
                'metric_name': metric_name,
                'value': value,
                'expires_at': expires_at,
            }
        )
        return cache