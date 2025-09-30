from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import User, SystemSettings
from .decorators import role_required
from .mixins import RolePermissionMixin


@login_required
def dashboard_view(request):
    """
    Main dashboard - shows role-specific information.
    """
    user = request.user
    context = {
        'user': user,
        'page_title': 'Dashboard',
    }
    
    # Import models (avoid circular imports)
    try:
        from apps.vehicles.models import Vehicle
        from apps.clients.models import Client as ClientModel
        from apps.payments.models import Payment, InstallmentPlan
        from apps.expenses.models import Expense
        
        # Common statistics
        total_vehicles = Vehicle.objects.count()
        available_vehicles = Vehicle.objects.filter(status='available').count()
        sold_vehicles = Vehicle.objects.filter(status='sold').count()
        total_clients = ClientModel.objects.count()
        
        # Financial overview
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        # Payments this month
        monthly_revenue = Payment.objects.filter(
            payment_date__gte=current_month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Pending installments
        pending_installments = InstallmentPlan.objects.filter(
            is_completed=False
        ).count()
        
        # Expenses this month
        monthly_expenses = Expense.objects.filter(
            date__gte=current_month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        context.update({
            'total_vehicles': total_vehicles,
            'available_vehicles': available_vehicles,
            'sold_vehicles': sold_vehicles,
            'total_clients': total_clients,
            'monthly_revenue': monthly_revenue,
            'pending_installments': pending_installments,
            'monthly_expenses': monthly_expenses,
            'net_profit': monthly_revenue - monthly_expenses,
        })
        
        # Role-specific data
        if user.role == 'admin' or user.role == 'manager':
            # Admin/Manager: Full overview
            context['recent_payments'] = Payment.objects.select_related('client').order_by('-payment_date')[:5]
            context['recent_clients'] = ClientModel.objects.order_by('-created_at')[:5]
            context['low_stock_vehicles'] = Vehicle.objects.filter(status='available').count()
            
        elif user.role == 'sales':
            # Sales: Focus on sales and clients
            context['my_clients'] = ClientModel.objects.filter(
                assigned_to=user
            ).count()
            context['recent_sales'] = Vehicle.objects.filter(
                status='sold',
                sold_by=user
            ).order_by('-updated_at')[:5]
            
        elif user.role == 'accountant':
            # Accountant: Financial focus
            overdue_payments = InstallmentPlan.objects.filter(
                next_payment_date__lt=today,
                is_completed=False
            ).count()
            context['overdue_payments'] = overdue_payments
            context['recent_transactions'] = Payment.objects.order_by('-payment_date')[:10]
            
        elif user.role == 'auctioneer':
            # Auctioneer: Repossessed and auction vehicles
            from apps.repossessions.models import RepossessedVehicle
            from apps.auctions.models import Auction
            
            context['repossessed_count'] = RepossessedVehicle.objects.filter(
                status='active'
            ).count()
            context['pending_auctions'] = Auction.objects.filter(
                status='pending'
            ).count()
    
    except ImportError:
        # Apps not yet created
        pass
    
    # Select appropriate dashboard template based on role
    template_name = f'core/dashboards/{user.role}_dashboard.html'
    
    # Fallback to general dashboard if role-specific doesn't exist
    try:
        return render(request, template_name, context)
    except:
        return render(request, 'core/dashboard.html', context)


@login_required
def profile_view(request):
    """
    User profile view and edit.
    """
    if request.method == 'POST':
        user = request.user
        
        # Update basic info
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.address = request.POST.get('address', user.address)
        
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('core:profile')
    
    context = {
        'page_title': 'My Profile',
    }
    return render(request, 'core/profile.html', context)


@login_required
@role_required(['admin'])
def user_list_view(request):
    """
    List all users (Admin only).
    """
    users = User.objects.all().order_by('-date_joined')
    
    # Filter by role
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'users': users,
        'page_title': 'User Management',
        'role_choices': User.ROLE_CHOICES,
    }
    return render(request, 'core/user_list.html', context)


@login_required
@role_required(['admin'])
def user_create_view(request):
    """
    Create new user (Admin only).
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        phone = request.POST.get('phone')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists!')
            return redirect('core:user_create')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone,
        )
        
        messages.success(request, f'User {username} created successfully!')
        return redirect('core:user_list')
    
    context = {
        'page_title': 'Create User',
        'role_choices': User.ROLE_CHOICES,
    }
    return render(request, 'core/user_form.html', context)


@login_required
@role_required(['admin'])
def settings_view(request):
    """
    System settings management (Admin only).
    """
    settings = SystemSettings.get_settings()
    
    if request.method == 'POST':
        settings.default_interest_rate = request.POST.get('default_interest_rate')
        settings.late_payment_penalty = request.POST.get('late_payment_penalty')
        settings.payment_reminder_days = request.POST.get('payment_reminder_days')
        settings.insurance_expiry_days = request.POST.get('insurance_expiry_days')
        settings.currency_symbol = request.POST.get('currency_symbol')
        settings.currency_code = request.POST.get('currency_code')
        settings.updated_by = request.user
        settings.save()
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('core:settings')
    
    context = {
        'settings': settings,
        'page_title': 'System Settings',
    }
    return render(request, 'core/settings.html', context)


def home_view(request):
    """
    Public home page (before login).
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    return render(request, 'core/home.html', {
        'page_title': 'Welcome',
    })