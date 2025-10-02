"""
Reports App - Forms
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Report,
    ReportTemplate,
    ReportWidget,
    SavedReport
)

User = get_user_model()


# ============================================================================
# REPORT FORMS
# ============================================================================

class ReportForm(forms.ModelForm):
    """Form for creating and updating reports"""
    
    class Meta:
        model = Report
        fields = [
            'name',
            'description',
            'report_type',
            'template',
            'query_config',
            'date_range_type',
            'custom_date_from',
            'custom_date_to',
            'output_format',
            'include_charts',
            'include_summary',
            'include_details',
            'is_scheduled',
            'frequency',
            'schedule_time',
            'schedule_day',
            'recipients',
            'email_recipients',
            'send_email',
            'is_public',
            'allowed_users',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Report name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Report description...'
            }),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'query_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '{"filters": {}, "groupby": []}'
            }),
            'date_range_type': forms.Select(attrs={'class': 'form-control'}),
            'custom_date_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'custom_date_to': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'output_format': forms.Select(attrs={'class': 'form-control'}),
            'include_charts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_summary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_details': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_scheduled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'schedule_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'schedule_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '31'
            }),
            'recipients': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '5'
            }),
            'email_recipients': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'email1@example.com, email2@example.com'
            }),
            'send_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allowed_users': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': '5'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate date range
        date_range_type = cleaned_data.get('date_range_type')
        custom_date_from = cleaned_data.get('custom_date_from')
        custom_date_to = cleaned_data.get('custom_date_to')
        
        if date_range_type == 'custom':
            if not custom_date_from or not custom_date_to:
                raise ValidationError('Custom date range requires both from and to dates.')
            
            if custom_date_from > custom_date_to:
                raise ValidationError('From date must be before to date.')
        
        # Validate scheduling
        is_scheduled = cleaned_data.get('is_scheduled')
        frequency = cleaned_data.get('frequency')
        schedule_time = cleaned_data.get('schedule_time')
        
        if is_scheduled:
            if not frequency or frequency == 'once':
                raise ValidationError('Scheduled reports must have a recurring frequency.')
            
            if not schedule_time:
                raise ValidationError('Schedule time is required for scheduled reports.')
        
        return cleaned_data
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Check for duplicate names
        qs = Report.objects.filter(name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError('A report with this name already exists.')
        
        return name


class QuickReportForm(forms.ModelForm):
    """Simplified form for quick report creation"""
    
    class Meta:
        model = Report
        fields = [
            'name',
            'report_type',
            'date_range_type',
            'output_format',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Report name'
            }),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'date_range_type': forms.Select(attrs={'class': 'form-control'}),
            'output_format': forms.Select(attrs={'class': 'form-control'}),
        }


class ReportFilterForm(forms.Form):
    """Form for filtering reports"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search reports...'
        })
    )
    report_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + list(Report.REPORT_TYPE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_scheduled = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('true', 'Scheduled'), ('false', 'Not Scheduled')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    output_format = forms.ChoiceField(
        required=False,
        choices=[('', 'All Formats')] + list(Report.OUTPUT_FORMAT_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ReportExecutionForm(forms.Form):
    """Form for executing a report with custom parameters"""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    output_format = forms.ChoiceField(
        choices=Report.OUTPUT_FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_details = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                raise ValidationError('From date must be before to date.')
        
        return cleaned_data


# ============================================================================
# REPORT TEMPLATE FORMS
# ============================================================================

class ReportTemplateForm(forms.ModelForm):
    """Form for creating and updating report templates"""
    
    class Meta:
        model = ReportTemplate
        fields = [
            'name',
            'description',
            'report_type',
            'layout',
            'columns',
            'grouping',
            'sorting',
            'aggregations',
            'header_template',
            'footer_template',
            'css_styles',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Template name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Template description...'
            }),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'layout': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'standard, detailed, summary, etc.'
            }),
            'columns': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '["column1", "column2", "column3"]'
            }),
            'grouping': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '{"by": "field_name"}'
            }),
            'sorting': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '{"by": "field_name", "order": "asc"}'
            }),
            'aggregations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '[{"field": "amount", "function": "sum"}]'
            }),
            'header_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Header HTML template...'
            }),
            'footer_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Footer HTML template...'
            }),
            'css_styles': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Custom CSS styles...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Check for duplicate names
        qs = ReportTemplate.objects.filter(name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError('A template with this name already exists.')
        
        return name


# ============================================================================
# REPORT WIDGET FORMS
# ============================================================================

class ReportWidgetForm(forms.ModelForm):
    """Form for creating and updating report widgets"""
    
    class Meta:
        model = ReportWidget
        fields = [
            'name',
            'description',
            'widget_type',
            'chart_type',
            'report',
            'data_source',
            'query_config',
            'refresh_interval',
            'width',
            'height',
            'order',
            'is_public',
            'allowed_users',
            'is_active',
        ]
        widgets = {
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
            'report': forms.Select(attrs={'class': 'form-control'}),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Vehicle, Payment, etc.'
            }),
            'query_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"filters": {}, "aggregation": "count"}'
            }),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '60'
            }),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '12'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '100'
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
# SAVED REPORT FORMS
# ============================================================================

class SavedReportForm(forms.ModelForm):
    """Form for customizing saved reports"""
    
    class Meta:
        model = SavedReport
        fields = ['custom_name', 'custom_parameters']
        widgets = {
            'custom_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Custom name (optional)'
            }),
            'custom_parameters': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"custom": "parameters"}'
            }),
        }


# ============================================================================
# SCHEDULING FORMS
# ============================================================================

class ScheduleReportForm(forms.Form):
    """Form for scheduling a report"""
    
    frequency = forms.ChoiceField(
        choices=[choice for choice in Report.FREQUENCY_CHOICES if choice[0] != 'once'],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    schedule_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
    )
    schedule_day = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Day of month (for monthly reports)'
        }),
        help_text='For monthly reports only'
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '5'
        })
    )
    email_recipients = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional emails (comma-separated)'
        })
    )


# ============================================================================
# REPORT BUILDER FORMS
# ============================================================================

class ReportBuilderForm(forms.Form):
    """Interactive report builder form"""
    
    # Step 1: Basic Info
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Report name'
        })
    )
    report_type = forms.ChoiceField(
        choices=Report.REPORT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Step 2: Data Selection
    date_range_type = forms.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_quarter', 'Last Quarter'),
            ('last_year', 'Last Year'),
            ('month_to_date', 'Month to Date'),
            ('year_to_date', 'Year to Date'),
            ('custom', 'Custom Range'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    custom_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    custom_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # Step 3: Output Options
    output_format = forms.ChoiceField(
        choices=Report.OUTPUT_FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Step 4: Scheduling (optional)
    schedule_report = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    frequency = forms.ChoiceField(
        required=False,
        choices=[('', 'Select frequency')] + [choice for choice in Report.FREQUENCY_CHOICES if choice[0] != 'once'],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate custom date range
        date_range_type = cleaned_data.get('date_range_type')
        if date_range_type == 'custom':
            date_from = cleaned_data.get('custom_date_from')
            date_to = cleaned_data.get('custom_date_to')
            
            if not date_from or not date_to:
                raise ValidationError('Custom date range requires both from and to dates.')
            
            if date_from > date_to:
                raise ValidationError('From date must be before to date.')
        
        # Validate scheduling
        schedule_report = cleaned_data.get('schedule_report')
        frequency = cleaned_data.get('frequency')
        
        if schedule_report and not frequency:
            raise ValidationError('Frequency is required for scheduled reports.')
        
        return cleaned_data


# ============================================================================
# EXPORT FORMS
# ============================================================================

class ExportReportForm(forms.Form):
    """Form for exporting report results"""
    
    format = forms.ChoiceField(
        choices=Report.OUTPUT_FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    include_raw_data = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Include raw data in addition to summary'
    )


# ============================================================================
# SHARE REPORT FORM
# ============================================================================

class ShareReportForm(forms.Form):
    """Form for sharing reports with users"""
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text='Select users to share this report with'
    )
    make_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Make this report accessible to all users'
    )