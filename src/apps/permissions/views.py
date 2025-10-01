"""
Permissions Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import RolePermission, PermissionHistory
from .forms import (
    RolePermissionForm, BulkPermissionForm,
    PermissionSearchForm, RoleModuleMatrixForm
)
from utils.decorators import superuser_required
from utils.constants import UserRole, ModuleName, AccessLevel


@login_required
@superuser_required
def permission_list_view(request):
    """List all permissions with search and filter"""
    permissions = RolePermission.objects.all().select_related('created_by')
    
    # Search and filter
    form = PermissionSearchForm(request.GET)
    
    if form.is_valid():
        role = form.cleaned_data.get('role')
        module = form.cleaned_data.get('module')
        access_level = form.cleaned_data.get('access_level')
        status = form.cleaned_data.get('status')
        
        if role:
            permissions = permissions.filter(role=role)
        
        if module:
            permissions = permissions.filter(module_name=module)
        
        if access_level:
            permissions = permissions.filter(access_level=access_level)
        
        if status == 'active':
            permissions = permissions.filter(is_active=True)
        elif status == 'inactive':
            permissions = permissions.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(permissions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_permissions': permissions.count(),
    }
    return render(request, 'permissions/permission_list.html', context)


@login_required
@superuser_required
def permission_detail_view(request, pk):
    """View permission details"""
    permission = get_object_or_404(RolePermission, pk=pk)
    
    # Get history
    history = PermissionHistory.objects.filter(permission=permission)[:10]
    
    context = {
        'permission': permission,
        'history': history,
    }
    return render(request, 'permissions/permission_detail.html', context)


@login_required
@superuser_required
def permission_create_view(request):
    """Create new permission"""
    if request.method == 'POST':
        form = RolePermissionForm(request.POST)
        if form.is_valid():
            permission = form.save(commit=False)
            permission.created_by = request.user
            permission.save()
            
            # Log creation
            PermissionHistory.objects.create(
                permission=permission,
                changed_by=request.user,
                action='created',
                new_value={
                    'access_level': permission.access_level,
                    'can_create': permission.can_create,
                    'can_edit': permission.can_edit,
                    'can_delete': permission.can_delete,
                    'can_export': permission.can_export,
                }
            )
            
            messages.success(request, f'Permission created successfully!')
            return redirect('permissions:list')
    else:
        form = RolePermissionForm()
    
    context = {
        'form': form,
        'title': 'Create Permission',
    }
    return render(request, 'permissions/permission_form.html', context)


@login_required
@superuser_required
def permission_update_view(request, pk):
    """Update existing permission"""
    permission = get_object_or_404(RolePermission, pk=pk)
    
    # Store old values
    old_value = {
        'access_level': permission.access_level,
        'can_create': permission.can_create,
        'can_edit': permission.can_edit,
        'can_delete': permission.can_delete,
        'can_export': permission.can_export,
    }
    
    if request.method == 'POST':
        form = RolePermissionForm(request.POST, instance=permission)
        if form.is_valid():
            permission = form.save()
            
            # Log update
            PermissionHistory.objects.create(
                permission=permission,
                changed_by=request.user,
                action='updated',
                old_value=old_value,
                new_value={
                    'access_level': permission.access_level,
                    'can_create': permission.can_create,
                    'can_edit': permission.can_edit,
                    'can_delete': permission.can_delete,
                    'can_export': permission.can_export,
                }
            )
            
            messages.success(request, f'Permission updated successfully!')
            return redirect('permissions:detail', pk=permission.pk)
    else:
        form = RolePermissionForm(instance=permission)
    
    context = {
        'form': form,
        'permission': permission,
        'title': 'Edit Permission',
    }
    return render(request, 'permissions/permission_form.html', context)


@login_required
@superuser_required
def permission_delete_view(request, pk):
    """Delete permission"""
    permission = get_object_or_404(RolePermission, pk=pk)
    
    if request.method == 'POST':
        # Log deletion before deleting
        PermissionHistory.objects.create(
            permission=permission,
            changed_by=request.user,
            action='deleted',
            old_value={
                'role': permission.role,
                'module_name': permission.module_name,
                'access_level': permission.access_level,
            }
        )
        
        permission_info = f"{permission.get_role_display()} - {permission.get_module_name_display()}"
        permission.delete()
        messages.success(request, f'Permission "{permission_info}" deleted successfully!')
        return redirect('permissions:list')
    
    context = {
        'permission': permission,
    }
    return render(request, 'permissions/permission_confirm_delete.html', context)


@login_required
@superuser_required
def permission_toggle_status_view(request, pk):
    """Toggle permission active status"""
    permission = get_object_or_404(RolePermission, pk=pk)
    
    old_status = permission.is_active
    permission.is_active = not permission.is_active
    permission.save()
    
    # Log status change
    action = 'activated' if permission.is_active else 'deactivated'
    PermissionHistory.objects.create(
        permission=permission,
        changed_by=request.user,
        action=action
    )
    
    status = 'activated' if permission.is_active else 'deactivated'
    messages.success(request, f'Permission has been {status}.')
    
    return redirect('permissions:detail', pk=permission.pk)


@login_required
@superuser_required
def bulk_permission_update_view(request):
    """Bulk update permissions for a role"""
    if request.method == 'POST':
        form = BulkPermissionForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            access_level = form.cleaned_data['access_level']
            can_create = form.cleaned_data['can_create']
            can_edit = form.cleaned_data['can_edit']
            can_delete = form.cleaned_data['can_delete']
            can_export = form.cleaned_data['can_export']
            
            # Update all permissions for this role
            permissions = RolePermission.objects.filter(role=role)
            count = permissions.update(
                access_level=access_level,
                can_create=can_create,
                can_edit=can_edit,
                can_delete=can_delete,
                can_export=can_export
            )
            
            messages.success(request, f'{count} permissions updated for {dict(UserRole.CHOICES)[role]}!')
            return redirect('permissions:list')
    else:
        form = BulkPermissionForm()
    
    context = {
        'form': form,
        'title': 'Bulk Update Permissions',
    }
    return render(request, 'permissions/bulk_update_form.html', context)


@login_required
@superuser_required
def role_matrix_view(request, role=None):
    """View/edit permissions in matrix format for a role"""
    if not role:
        # Show role selection
        roles = UserRole.CHOICES
        context = {
            'roles': roles,
        }
        return render(request, 'permissions/role_selection.html', context)
    
    if request.method == 'POST':
        form = RoleModuleMatrixForm(role, request.POST)
        if form.is_valid():
            # Update permissions
            updated_count = 0
            for module_code, module_name in ModuleName.CHOICES:
                field_name = f'module_{module_code}'
                access_level = form.cleaned_data.get(field_name)
                
                if access_level:
                    permission, created = RolePermission.objects.update_or_create(
                        role=role,
                        module_name=module_code,
                        defaults={
                            'access_level': access_level,
                            'can_create': access_level in [AccessLevel.READ_WRITE, AccessLevel.FULL_ACCESS],
                            'can_edit': access_level in [AccessLevel.READ_WRITE, AccessLevel.FULL_ACCESS],
                            'can_delete': access_level == AccessLevel.FULL_ACCESS,
                            'can_export': access_level != AccessLevel.NO_ACCESS,
                            'is_active': True,
                        }
                    )
                    
                    if not created:
                        # Log update
                        PermissionHistory.objects.create(
                            permission=permission,
                            changed_by=request.user,
                            action='updated',
                            new_value={'access_level': access_level}
                        )
                    
                    updated_count += 1
            
            messages.success(request, f'{updated_count} permissions updated for {dict(UserRole.CHOICES)[role]}!')
            return redirect('permissions:role_matrix', role=role)
    else:
        form = RoleModuleMatrixForm(role)
    
    # Get current permissions for this role
    permissions = RolePermission.objects.filter(role=role)
    
    context = {
        'form': form,
        'role': role,
        'role_display': dict(UserRole.CHOICES)[role],
        'permissions': permissions,
        'modules': ModuleName.CHOICES,
    }
    return render(request, 'permissions/role_matrix.html', context)


@login_required
@superuser_required
def initialize_permissions_view(request):
    """Initialize default permissions for all roles"""
    if request.method == 'POST':
        count = RolePermission.initialize_default_permissions()
        messages.success(request, f'{count} default permissions created!')
        return redirect('permissions:list')
    
    return render(request, 'permissions/initialize_confirm.html')


@login_required
@superuser_required
def permission_history_view(request, pk):
    """View full history for a permission"""
    permission = get_object_or_404(RolePermission, pk=pk)
    history = PermissionHistory.objects.filter(permission=permission)
    
    # Pagination
    paginator = Paginator(history, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'permission': permission,
        'page_obj': page_obj,
    }
    return render(request, 'permissions/permission_history.html', context)