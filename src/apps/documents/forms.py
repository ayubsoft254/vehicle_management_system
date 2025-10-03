"""
Forms for the documents app.
Handles document upload, categorization, version control, and sharing.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Document, DocumentCategory, DocumentShare, DocumentTag
)
import os

User = get_user_model()


class DocumentForm(forms.ModelForm):
    """Form for uploading and managing documents."""
    
    # Additional fields not in model
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas',
            'data-role': 'tagsinput'
        }),
        help_text='Separate tags with commas'
    )
    
    notify_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select users to notify'
        }),
        help_text='Users who will be notified about this document'
    )
    
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'category', 'file', 
            'related_vehicle', 'related_client', 'is_public',
            'is_archived', 'expiry_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter document description'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.txt'
            }),
            'related_vehicle': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select related vehicle (optional)'
            }),
            'related_client': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select related client (optional)'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_archived': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make related fields optional
        self.fields['related_vehicle'].required = False
        self.fields['related_client'].required = False
        
        # Set initial tags if editing
        if self.instance.pk:
            tags = self.instance.tags.all()
            self.fields['tags'].initial = ', '.join([tag.name for tag in tags])
    
    def clean_file(self):
        """Validate file upload."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 50MB)
            if file.size > 50 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 50MB.')
            
            # Check file extension
            allowed_extensions = [
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
                '.ppt', '.pptx', '.txt', '.csv',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp'
            ]
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in allowed_extensions:
                raise ValidationError(
                    f'File type {ext} is not allowed. '
                    f'Allowed types: {", ".join(allowed_extensions)}'
                )
        
        return file
    
    def clean_expiry_date(self):
        """Validate expiry date."""
        expiry_date = self.cleaned_data.get('expiry_date')
        
        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError('Expiry date cannot be in the past.')
        
        return expiry_date
    
    def clean(self):
        """Additional validation."""
        cleaned_data = super().clean()
        
        # At least one relationship or category must be specified
        category = cleaned_data.get('category')
        related_vehicle = cleaned_data.get('related_vehicle')
        related_client = cleaned_data.get('related_client')
        
        if not category and not related_vehicle and not related_client:
            raise ValidationError(
                'Please specify at least a category, related vehicle, or related client.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save document and handle tags."""
        document = super().save(commit=False)
        
        # Set uploaded_by if user is provided
        if self.user and not document.pk:
            document.uploaded_by = self.user
        
        if commit:
            document.save()
            
            # Handle tags
            tags_input = self.cleaned_data.get('tags', '')
            if tags_input:
                tag_names = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
                document.tags.clear()
                for tag_name in tag_names:
                    tag, created = DocumentTag.objects.get_or_create(
                        name=tag_name.lower()
                    )
                    document.tags.add(tag)
        
        return document


class DocumentCategoryForm(forms.ModelForm):
    """Form for managing document categories."""
    
    class Meta:
        model = DocumentCategory
        fields = ['name', 'description', 'parent', 'icon', 'color']
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
            'parent': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select parent category (optional)'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Icon class (e.g., fa-folder)'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].required = False
        
        # Prevent circular references
        if self.instance.pk:
            self.fields['parent'].queryset = DocumentCategory.objects.exclude(
                pk=self.instance.pk
            ).exclude(
                parent=self.instance
            )


class DocumentVersionForm(forms.ModelForm):
    """Form for uploading new document versions."""
    
    version_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe the changes in this version'
        }),
        help_text='Explain what changed in this version'
    )
    
    class Meta:
        model = DocumentVersion
        fields = ['file', 'version_notes']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'required': True
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.document = kwargs.pop('document', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_file(self):
        """Validate file upload."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 50MB)
            if file.size > 50 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 50MB.')
            
            # Should be same type as original document
            if self.document:
                original_ext = os.path.splitext(self.document.file.name)[1].lower()
                new_ext = os.path.splitext(file.name)[1].lower()
                
                if original_ext != new_ext:
                    raise ValidationError(
                        f'New version must be the same file type as original ({original_ext}).'
                    )
        
        return file
    
    def save(self, commit=True):
        """Save new version."""
        version = super().save(commit=False)
        
        if self.document:
            version.document = self.document
        
        if self.user:
            version.uploaded_by = self.user
        
        # Auto-increment version number
        if self.document:
            last_version = self.document.versions.order_by('-version_number').first()
            if last_version:
                version.version_number = last_version.version_number + 1
            else:
                version.version_number = 1
        
        if commit:
            version.save()
        
        return version


class DocumentShareForm(forms.ModelForm):
    """Form for sharing documents with users."""
    
    class Meta:
        model = DocumentShare
        fields = ['shared_with', 'can_edit', 'can_delete', 'expires_at']
        widgets = {
            'shared_with': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select user'
            }),
            'can_edit': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'can_delete': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.document = kwargs.pop('document', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Don't allow sharing with document owner
        if self.document and self.document.uploaded_by:
            self.fields['shared_with'].queryset = User.objects.filter(
                is_active=True
            ).exclude(pk=self.document.uploaded_by.pk)
        
        self.fields['expires_at'].required = False
    
    def clean_expires_at(self):
        """Validate expiration date."""
        expires_at = self.cleaned_data.get('expires_at')
        
        if expires_at and expires_at < timezone.now():
            raise ValidationError('Expiration date cannot be in the past.')
        
        return expires_at
    
    def clean(self):
        """Check for duplicate shares."""
        cleaned_data = super().clean()
        shared_with = cleaned_data.get('shared_with')
        
        if self.document and shared_with:
            existing = DocumentShare.objects.filter(
                document=self.document,
                shared_with=shared_with
            ).exists()
            
            if existing:
                raise ValidationError(
                    f'Document is already shared with {shared_with.get_full_name() or shared_with.username}.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save share record."""
        share = super().save(commit=False)
        
        if self.document:
            share.document = self.document
        
        if self.user:
            share.shared_by = self.user
        
        if commit:
            share.save()
        
        return share


class DocumentCommentForm(forms.ModelForm):
    """Form for adding comments to documents."""
    
    class Meta:
        model = DocumentComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add your comment...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.document = kwargs.pop('document', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        """Save comment."""
        comment = super().save(commit=False)
        
        if self.document:
            comment.document = self.document
        
        if self.user:
            comment.user = self.user
        
        if commit:
            comment.save()
        
        return comment


class DocumentSearchForm(forms.Form):
    """Form for searching documents."""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search documents...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=DocumentCategory.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-placeholder': 'All categories'
        })
    )
    
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by tags',
            'data-role': 'tagsinput'
        })
    )
    
    uploaded_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Any uploader'
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
    
    is_archived = forms.NullBooleanField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        },
        choices=[
            ('', 'All documents'),
            ('false', 'Active only'),
            ('true', 'Archived only')
        ])
    )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date must be before end date.')
        
        return cleaned_data


class BulkDocumentActionForm(forms.Form):
    """Form for bulk actions on documents."""
    
    ACTION_CHOICES = [
        ('archive', 'Archive'),
        ('unarchive', 'Unarchive'),
        ('delete', 'Delete'),
        ('change_category', 'Change Category'),
        ('add_tags', 'Add Tags'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    document_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    # Optional fields for specific actions
    new_category = forms.ModelChoiceField(
        queryset=DocumentCategory.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas'
        })
    )
    
    def clean_document_ids(self):
        """Parse and validate document IDs."""
        ids_str = self.cleaned_data.get('document_ids', '')
        try:
            ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
            if not ids:
                raise ValidationError('No documents selected.')
            return ids
        except ValueError:
            raise ValidationError('Invalid document IDs.')
    
    def clean(self):
        """Validate required fields based on action."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'change_category' and not cleaned_data.get('new_category'):
            raise ValidationError('Please select a category.')
        
        if action == 'add_tags' and not cleaned_data.get('tags'):
            raise ValidationError('Please enter at least one tag.')
        
        return cleaned_data