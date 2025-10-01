"""
Permissions Forms
"""
from django import forms
from .models import RolePermission
from utils.constants import UserRole, ModuleName, AccessLevel


class RolePermissionForm(forms.ModelForm):
    """Form for creating/editing role permissions"""
    
    class Meta:
        model = RolePermission
        fields = [
            'role', 'module_name', 'access_level',
            'can_create', 'can_edit', 'can_delete', 'can_export',
            'description', 'is_active'
        ]
        widgets = {
            'role': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'module_name': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'can_create': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'can_edit': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'can_delete': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'can_export': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Optional description for this permission...'
            }),
        }
        labels = {
            'role': 'User Role',
            'module_name': 'Module',
            'access_level': 'Access Level',
            'can_create': 'Can Create Records',
            'can_edit': 'Can Edit Records',
            'can_delete': 'Can Delete Records',
            'can_export': 'Can Export Data',
            'is_active': 'Active',
            'description': 'Description',
        }
        help_texts = {
            'role': 'Select the user role for this permission',
            'module_name': 'Select the module to configure access',
            'access_level': 'Base access level for this role/module combination',
            'can_create': 'Allow creating new records',
            'can_edit': 'Allow editing existing records',
            'can_delete': 'Allow deleting records',
            'can_export': 'Allow exporting data to PDF/Excel',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        access_level = cleaned_data.get('access_level')
        role = cleaned_data.get('role')
        module_name = cleaned_data.get('module_name')
        
        # Check for duplicate role-module combination
        if self.instance.pk is None:  # Only for new permissions
            if RolePermission.objects.filter(role=role, module_name=module_name).exists():
                raise forms.ValidationError(
                    f'Permission already exists for {dict(UserRole.CHOICES).get(role)} - {dict(ModuleName.CHOICES).get(module_name)}'
                )
        
        # Auto-adjust permissions based on access level
        if access_level == AccessLevel.NO_ACCESS:
            cleaned_data['can_create'] = False
            cleaned_data['can_edit'] = False
            cleaned_data['can_delete'] = False
            cleaned_data['can_export'] = False
        elif access_level == AccessLevel.READ_ONLY:
            cleaned_data['can_create'] = False
            cleaned_data['can_edit'] = False
            cleaned_data['can_delete'] = False
        elif access_level == AccessLevel.FULL_ACCESS:
            cleaned_data['can_create'] = True
            cleaned_data['can_edit'] = True
            cleaned_data['can_delete'] = True
            cleaned_data['can_export'] = True
        
        return cleaned_data


class BulkPermissionForm(forms.Form):
    """Form for bulk updating permissions for a role"""
    
    role = forms.ChoiceField(
        label='Role',
        choices=UserRole.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        }),
        help_text='Select the role to update permissions for'
    )
    
    access_level = forms.ChoiceField(
        label='Access Level for All Modules',
        choices=AccessLevel.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        }),
        help_text='This access level will be applied to all modules for the selected role'
    )
    
    can_create = forms.BooleanField(
        label='Can Create',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Allow creating new records'
    )
    
    can_edit = forms.BooleanField(
        label='Can Edit',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Allow editing existing records'
    )
    
    can_delete = forms.BooleanField(
        label='Can Delete',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Allow deleting records'
    )
    
    can_export = forms.BooleanField(
        label='Can Export',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        help_text='Allow exporting data'
    )


class PermissionSearchForm(forms.Form):
    """Form for searching/filtering permissions"""
    
    role = forms.ChoiceField(
        label='Role',
        choices=[('', 'All Roles')] + list(UserRole.CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    module = forms.ChoiceField(
        label='Module',
        choices=[('', 'All Modules')] + list(ModuleName.CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    access_level = forms.ChoiceField(
        label='Access Level',
        choices=[('', 'All Levels')] + list(AccessLevel.CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    status = forms.ChoiceField(
        label='Status',
        choices=[
            ('', 'All'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )


class RoleModuleMatrixForm(forms.Form):
    """
    Dynamic form for managing permissions in a matrix view
    Displays all modules for a selected role
    """
    
    def __init__(self, role=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if role:
            # Get all modules
            for module_code, module_name in ModuleName.CHOICES:
                # Create a select field for each module
                field_name = f'module_{module_code}'
                self.fields[field_name] = forms.ChoiceField(
                    label=module_name,
                    choices=AccessLevel.CHOICES,
                    required=False,
                    widget=forms.Select(attrs={
                        'class': 'px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
                    })
                )
                
                # Set initial value from existing permission
                try:
                    permission = RolePermission.objects.get(
                        role=role,
                        module_name=module_code
                    )
                    self.fields[field_name].initial = permission.access_level
                except RolePermission.DoesNotExist:
                    self.fields[field_name].initial = AccessLevel.NO_ACCESS


class QuickAccessForm(forms.Form):
    """
    Quick form to check what a user can do in a specific module
    """
    role = forms.ChoiceField(
        label='Role',
        choices=UserRole.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    module = forms.ChoiceField(
        label='Module',
        choices=ModuleName.CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )