"""
Forms for the expenses app.
Handles expense submission, approval, reports, and category management.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    Expense, ExpenseCategory, ExpenseReceipt, ExpenseReport,
    ExpenseTag, RecurringExpense, ExpenseApprovalWorkflow
)

User = get_user_model()


class ExpenseForm(forms.ModelForm):
    """Form for creating and editing expenses."""
    
    # Additional fields
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas',
            'data-role': 'tagsinput'
        }),
        help_text='Separate tags with commas'
    )
    
    class Meta:
        model = Expense
        fields = [
            'title', 'description', 'category', 'amount', 'currency',
            'tax_amount', 'expense_date', 'payment_method', 'vendor_name',
            'invoice_number', 'related_vehicle', 'related_client',
            'is_reimbursable', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter expense title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the expense'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'currency': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'KES'
            }),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00'
            }),
            'expense_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'vendor_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vendor/supplier name'
            }),
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice/receipt number'
            }),
            'related_vehicle': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select vehicle (optional)'
            }),
            'related_client': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select client (optional)'
            }),
            'is_reimbursable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make optional fields not required
        self.fields['related_vehicle'].required = False
        self.fields['related_client'].required = False
        self.fields['vendor_name'].required = False
        self.fields['invoice_number'].required = False
        self.fields['tax_amount'].required = False
        
        # Filter only active categories
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        
        # Set initial tags if editing
        if self.instance.pk:
            tags = self.instance.tags.all()
            self.fields['tags'].initial = ', '.join([tag.name for tag in tags])
    
    def clean_expense_date(self):
        """Validate expense date."""
        expense_date = self.cleaned_data.get('expense_date')
        
        if expense_date:
            # Can't be in the future
            if expense_date > date.today():
                raise ValidationError('Expense date cannot be in the future.')
            
            # Can't be too old (configurable, e.g., 1 year)
            one_year_ago = date.today() - timedelta(days=365)
            if expense_date < one_year_ago:
                raise ValidationError('Expense date cannot be more than 1 year old.')
        
        return expense_date
    
    def clean_amount(self):
        """Validate amount."""
        amount = self.cleaned_data.get('amount')
        
        if amount and amount <= 0:
            raise ValidationError('Amount must be greater than zero.')
        
        # Check against category budget if exists
        category = self.cleaned_data.get('category')
        if category and category.budget_limit:
            # Get total expenses for this category this month
            expense_date = self.cleaned_data.get('expense_date', date.today())
            total = category.get_total_expenses(
                start_date=expense_date.replace(day=1),
                end_date=expense_date
            )
            
            # Add current expense amount (exclude if editing)
            if self.instance.pk:
                total -= self.instance.amount
            total += amount
            
            if total > category.budget_limit:
                raise ValidationError(
                    f'This expense would exceed the category budget limit of '
                    f'{category.budget_limit} {self.cleaned_data.get("currency", "KES")}'
                )
        
        return amount
    
    def clean_tax_amount(self):
        """Validate tax amount."""
        tax_amount = self.cleaned_data.get('tax_amount', Decimal('0.00'))
        amount = self.cleaned_data.get('amount')
        
        if tax_amount and amount and tax_amount > amount:
            raise ValidationError('Tax amount cannot exceed the expense amount.')
        
        return tax_amount
    
    def save(self, commit=True):
        """Save expense and handle tags."""
        expense = super().save(commit=False)
        
        # Set submitted_by if creating new expense
        if self.user and not expense.pk:
            expense.submitted_by = self.user
        
        if commit:
            expense.save()
            
            # Handle tags
            tags_input = self.cleaned_data.get('tags', '')
            if tags_input:
                tag_names = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
                expense.tags.clear()
                for tag_name in tag_names:
                    tag, created = ExpenseTag.objects.get_or_create(
                        name=tag_name.lower()
                    )
                    expense.tags.add(tag)
        
        return expense


class ExpenseReceiptForm(forms.ModelForm):
    """Form for uploading expense receipts."""
    
    class Meta:
        model = ExpenseReceipt
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,application/pdf'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Receipt description (optional)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.expense = kwargs.pop('expense', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['description'].required = False
    
    def clean_file(self):
        """Validate file upload."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 10MB.')
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
            if file.content_type not in allowed_types:
                raise ValidationError(
                    'Only images (JPEG, PNG, GIF) and PDF files are allowed.'
                )
        
        return file
    
    def save(self, commit=True):
        """Save receipt with metadata."""
        receipt = super().save(commit=False)
        
        if self.expense:
            receipt.expense = self.expense
        
        if self.user:
            receipt.uploaded_by = self.user
        
        if receipt.file:
            receipt.file_name = receipt.file.name
            receipt.file_size = receipt.file.size
            receipt.file_type = receipt.file.content_type
        
        if commit:
            receipt.save()
        
        return receipt


class ExpenseApprovalForm(forms.Form):
    """Form for approving or rejecting expenses."""
    
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add comments (required for rejection)'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.expense = kwargs.pop('expense', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate approval action."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        comments = cleaned_data.get('comments')
        
        # Comments required for rejection
        if action == 'reject' and not comments:
            raise ValidationError('Comments are required when rejecting an expense.')
        
        # Check if expense can be approved/rejected
        if self.expense and self.expense.status != 'SUBMITTED':
            raise ValidationError(
                f'Cannot process expense with status: {self.expense.get_status_display()}'
            )
        
        return cleaned_data


class ExpenseCategoryForm(forms.ModelForm):
    """Form for managing expense categories."""
    
    class Meta:
        model = ExpenseCategory
        fields = [
            'name', 'description', 'code', 'parent', 'is_active',
            'requires_receipt', 'requires_approval', 'budget_limit',
            'icon', 'color'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Category description'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Accounting code (e.g., EXP-001)'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select parent category (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'requires_receipt': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'requires_approval': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'budget_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': 'Monthly budget limit'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Icon class (e.g., fa-gas-pump)'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['parent'].required = False
        self.fields['budget_limit'].required = False
        
        # Prevent circular references
        if self.instance.pk:
            self.fields['parent'].queryset = ExpenseCategory.objects.exclude(
                pk=self.instance.pk
            ).exclude(
                parent=self.instance
            )


class ExpenseReportForm(forms.ModelForm):
    """Form for creating expense reports."""
    
    class Meta:
        model = ExpenseReport
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Report title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Report description'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('End date must be after start date.')
            
            # Check if date range is not too large (e.g., max 1 year)
            if (end_date - start_date).days > 365:
                raise ValidationError('Date range cannot exceed 1 year.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save report."""
        report = super().save(commit=False)
        
        if self.user:
            report.submitted_by = self.user
        
        if commit:
            report.save()
        
        return report


class RecurringExpenseForm(forms.ModelForm):
    """Form for creating recurring expense templates."""
    
    class Meta:
        model = RecurringExpense
        fields = [
            'title', 'description', 'category', 'amount', 'currency',
            'frequency', 'start_date', 'end_date', 'vendor_name',
            'payment_method', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Recurring expense title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'currency': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'KES'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'vendor_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vendor name'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['end_date'].required = False
        self.fields['vendor_name'].required = False
        
        # Filter active categories
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
    
    def clean(self):
        """Validate dates."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError('End date must be after start date.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save recurring expense."""
        recurring = super().save(commit=False)
        
        if self.user:
            recurring.submitted_by = self.user
        
        if commit:
            recurring.save()
        
        return recurring


class ExpenseSearchForm(forms.Form):
    """Form for searching and filtering expenses."""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search expenses...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-placeholder': 'All categories'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(Expense.STATUS_CHOICES),
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
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
    
    min_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Min amount'
        })
    )
    
    max_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Max amount'
        })
    )
    
    submitted_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Any submitter'
        })
    )
    
    is_reimbursable = forms.NullBooleanField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        },
        choices=[
            ('', 'All expenses'),
            ('true', 'Reimbursable only'),
            ('false', 'Non-reimbursable only')
        ])
    )
    
    def clean(self):
        """Validate search criteria."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date must be before end date.')
        
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        if min_amount and max_amount and min_amount > max_amount:
            raise ValidationError('Minimum amount must be less than maximum amount.')
        
        return cleaned_data


class BulkExpenseActionForm(forms.Form):
    """Form for bulk actions on expenses."""
    
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('submit', 'Submit for Approval'),
        ('delete', 'Delete'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    expense_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Comments (required for rejection)'
        })
    )
    
    def clean_expense_ids(self):
        """Parse and validate expense IDs."""
        ids_str = self.cleaned_data.get('expense_ids', '')
        try:
            ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
            if not ids:
                raise ValidationError('No expenses selected.')
            return ids
        except ValueError:
            raise ValidationError('Invalid expense IDs.')
    
    def clean(self):
        """Validate bulk action."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        comments = cleaned_data.get('comments')
        
        if action == 'reject' and not comments:
            raise ValidationError('Comments are required when rejecting expenses.')
        
        return cleaned_data