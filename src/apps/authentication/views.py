"""
Authentication Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import User, UserProfile
from .forms import (
    CustomUserCreationForm, CustomUserChangeForm,
    UserProfileForm, UserSearchForm
)
from utils.decorators import role_required, superuser_required
from utils.constants import UserRole


@login_required
def profile_view(request):
    """View and edit user profile"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, request.FILES, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=user_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('authentication:profile')
    else:
        user_form = CustomUserChangeForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'authentication/profile.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def user_list_view(request):
    """List all users with search and filter"""
    users = User.objects.all().select_related('profile')
    
    # Search and filter
    form = UserSearchForm(request.GET)
    
    if form.is_valid():
        search = form.cleaned_data.get('search')
        role = form.cleaned_data.get('role')
        status = form.cleaned_data.get('status')
        
        if search:
            users = users.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(employee_id__icontains=search)
            )
        
        if role:
            users = users.filter(role=role)
        
        if status == 'active':
            users = users.filter(is_active=True)
        elif status == 'inactive':
            users = users.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_users': users.count(),
    }
    return render(request, 'authentication/user_list.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def user_detail_view(request, pk):
    """View user details"""
    user = get_object_or_404(User, pk=pk)
    
    context = {
        'user_obj': user,
    }
    return render(request, 'authentication/user_detail.html', context)


@login_required
@superuser_required
def user_create_view(request):
    """Create new user (Admin only)"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.get_full_name()} has been created successfully!')
            return redirect('authentication:user_list')
    else:
        form = CustomUserCreationForm()
    
    context = {
        'form': form,
        'title': 'Create New User',
    }
    return render(request, 'authentication/user_form.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def user_update_view(request, pk):
    """Update user information"""
    user = get_object_or_404(User, pk=pk)
    
    # Only admins can edit other admins
    if user.role == UserRole.ADMIN and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit administrator accounts.')
        return redirect('authentication:user_list')
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.get_full_name()} has been updated successfully!')
            return redirect('authentication:user_detail', pk=user.pk)
    else:
        form = CustomUserChangeForm(instance=user)
    
    context = {
        'form': form,
        'user_obj': user,
        'title': f'Edit User: {user.get_full_name()}',
    }
    return render(request, 'authentication/user_form.html', context)


@login_required
@superuser_required
def user_delete_view(request, pk):
    """Delete user (Admin only)"""
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('authentication:user_list')
    
    if request.method == 'POST':
        user_name = user.get_full_name()
        user.delete()
        messages.success(request, f'User {user_name} has been deleted successfully!')
        return redirect('authentication:user_list')
    
    context = {
        'user_obj': user,
    }
    return render(request, 'authentication/user_confirm_delete.html', context)


@login_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def user_toggle_status_view(request, pk):
    """Toggle user active status"""
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('authentication:user_list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.get_full_name()} has been {status}.')
    
    return redirect('authentication:user_detail', pk=user.pk)