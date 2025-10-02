"""
Dashboard App - Forms
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import (
    Dashboard,
    Widget,
    UserDashboardPreference,
    QuickAction,
    DashboardSnapshot
)

User = get_user_model()


# ============================================================================
# DASHBOARD FORMS
# ============================================================================

class DashboardForm(forms.ModelForm):
    """Form for creating and updating dashboards"""
    
    class Meta:
        model = Dashboard
        fields = [
            'name',
            'description',
            'layout',
            'columns',
            'is_public',
            'is_default',
            'shared_with',
            'auto_refresh',
            'refresh_interval',
            'theme',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dashboard name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dashboard description...'
            }),
            'layout': forms.Select(attrs={'class': 'form-control'}),
            'columns': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '24'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'shared_with': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '5'
            }),
            'auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '60'
            }),
            'theme': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Check for duplicate names for same user
        qs = Dashboard.objects.filter(
            name=name,
            created_by=self.instance.created_by if self.instance.pk else None
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError('You already have a dashboard with this name.')
        
        return name


class QuickDashboardForm(forms.ModelForm):
    """Simplified form for quick dashboard creation"""
    
    class Meta:
        model = Dashboard
        fields = ['name', 'layout', 'theme']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dashboard name'
            }),
            'layout': forms.Select(attrs={'class': 'form-control'}),
            'theme': forms.Select(attrs={'class': 'form-control'}),
        }


# ============================================================================
# WIDGET FORMS
# ============================================================================

class WidgetForm(forms.ModelForm):
    """Form for creating and updating widgets"""
    
    class Meta:
        model = Widget
        fields = [
            'dashboard',
            'name',
            'description',
            'widget_type',
            'chart_type',
            'data_source',
            'query_config',
            'position_x',
            'position_y',
            'width',
            'height',
            'size',
            'order',
            'show_title',
            'show_border',
            'title_color',
            'background_color',
            'auto_refresh',
            'refresh_interval',
            'custom_css',
            'custom_config',
            'is_active',
        ]
        widgets = {
            'dashboard': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Widget name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Widget description...'
            }),
            'widget_type': forms.Select(attrs={'class': 'form-control'}),
            'chart_type': forms.Select(attrs={'class': 'form-control'}),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Vehicle, Payment, Client'
            }),
            'query_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '{"filters": {}, "aggregation": "count"}'
            }),
            'position_x': forms.NumberInput(attrs={'class': 'form-control'}),
            'position_y': forms.NumberInput(attrs={'class': 'form-control'}),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '12'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '100'
            }),
            'size': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'show_title': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_border': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'title_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'background_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '60'
            }),
            'custom_css': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Custom CSS...'
            }),
            'custom_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"custom": "config"}'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class QuickWidgetForm(forms.ModelForm):
    """Simplified form for quick widget creation"""
    
    class Meta:
        model = Widget
        fields = [
            'name',
            'widget_type',
            'data_source',
            'size',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Widget name'
            }),
            'widget_type': forms.Select(attrs={'class': 'form-control'}),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Data source'
            }),
            'size': forms.Select(attrs={'class': 'form-control'}),
        }


class WidgetPositionForm(forms.Form):
    """Form for updating widget position"""
    
    widget_id = forms.UUIDField(widget=forms.HiddenInput())
    position_x = forms.IntegerField(min_value=0)
    position_y = forms.IntegerField(min_value=0)
    width = forms.IntegerField(min_value=1, max_value=12)
    height = forms.IntegerField(min_value=100)


# ============================================================================
# USER PREFERENCE FORMS
# ============================================================================

class UserDashboardPreferenceForm(forms.ModelForm):
    """Form for managing user dashboard preferences"""
    
    class Meta:
        model = UserDashboardPreference
        fields = [
            'default_dashboard',
            'theme',
            'compact_mode',
            'show_grid_lines',
            'default_refresh_interval',
            'enable_animations',
            'show_notifications',
            'show_quick_actions',
            'show_activity_feed',
        ]
        widgets = {
            'default_dashboard': forms.Select(attrs={'class': 'form-control'}),
            'theme': forms.Select(attrs={'class': 'form-control'}),
            'compact_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_grid_lines': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '60'
            }),
            'enable_animations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_quick_actions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_activity_feed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter dashboards to only those accessible by user
            self.fields['default_dashboard'].queryset = Dashboard.objects.for_user(user)


# ============================================================================
# QUICK ACTION FORMS
# ============================================================================

class QuickActionForm(forms.ModelForm):
    """Form for creating and updating quick actions"""
    
    class Meta:
        model = QuickAction
        fields = [
            'name',
            'description',
            'action_type',
            'action_url',
            'action_config',
            'icon',
            'color',
            'order',
            'is_public',
            'allowed_users',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Action name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Action description...'
            }),
            'action_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., link, modal, api_call'
            }),
            'action_url': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '/path/to/action'
            }),
            'action_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"key": "value"}'
            }),
            'icon': forms.Select(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allowed_users': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '5'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================================
# SNAPSHOT FORMS
# ============================================================================

class DashboardSnapshotForm(forms.ModelForm):
    """Form for creating dashboard snapshots"""
    
    class Meta:
        model = DashboardSnapshot
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Snapshot name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Snapshot description...'
            }),
        }


# ============================================================================
# FILTER & SEARCH FORMS
# ============================================================================

class DashboardFilterForm(forms.Form):
    """Form for filtering dashboards"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search dashboards...'
        })
    )
    layout = forms.ChoiceField(
        required=False,
        choices=[('', 'All Layouts')] + list(Dashboard.LAYOUT_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    theme = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Themes'),
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_public = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All'),
            ('true', 'Public'),
            ('false', 'Private')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class WidgetFilterForm(forms.Form):
    """Form for filtering widgets"""
    
    widget_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + list(Widget.WIDGET_TYPE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    size = forms.ChoiceField(
        required=False,
        choices=[('', 'All Sizes')] + list(Widget.SIZE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_active = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# ============================================================================
# SHARING FORMS
# ============================================================================

class ShareDashboardForm(forms.Form):
    """Form for sharing dashboards with users"""
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text='Select users to share this dashboard with'
    )
    make_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Make this dashboard accessible to all users'
    )


# ============================================================================
# LAYOUT MANAGEMENT FORMS
# ============================================================================

class DashboardLayoutForm(forms.Form):
    """Form for updating dashboard layout"""
    
    layout = forms.ChoiceField(
        choices=Dashboard.LAYOUT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    columns = forms.IntegerField(
        min_value=1,
        max_value=24,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class BatchWidgetUpdateForm(forms.Form):
    """Form for batch updating widgets"""
    
    widget_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    action = forms.ChoiceField(
        choices=[
            ('activate', 'Activate'),
            ('deactivate', 'Deactivate'),
            ('delete', 'Delete'),
            ('reset_position', 'Reset Position'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean_widget_ids(self):
        ids = self.cleaned_data.get('widget_ids')
        if ids:
            return [id.strip() for id in ids.split(',')]
        return []


# ============================================================================
# EXPORT & IMPORT FORMS
# ============================================================================

class ExportDashboardForm(forms.Form):
    """Form for exporting dashboard configuration"""
    
    include_widgets = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include widgets'
    )
    include_layout = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include layout settings'
    )
    format = forms.ChoiceField(
        choices=[
            ('json', 'JSON'),
            ('yaml', 'YAML'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ImportDashboardForm(forms.Form):
    """Form for importing dashboard configuration"""
    
    config_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        help_text='Upload JSON or YAML configuration file'
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Overwrite if dashboard with same name exists'
    )