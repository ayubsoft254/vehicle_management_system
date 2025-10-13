"""
Client Portal Views
Views for client-facing portal where clients can manage their accounts
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Prefetch, F, Max, Avg
from django.http import JsonResponse, Http404, FileResponse
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Client, ClientVehicle, ClientDocument
from apps.payments.models import Payment, InstallmentPlan, PaymentSchedule
from apps.vehicles.models import Vehicle
from apps.documents.models import Document
from apps.insurance.models import InsurancePolicy
from apps.auctions.models import Auction, Bid, AuctionParticipant, AuctionWatchlist
from utils.constants import UserRole, VehicleStatus
import json


# ==================== DECORATORS ====================

def client_required(view_func):
    """Decorator to ensure only clients can access the view"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access the client portal.')
            return redirect('account_login')
        
        if request.user.role != UserRole.CLIENT:
            messages.error(request, 'This area is only accessible to clients.')
            return redirect('dashboard:index')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def get_client_from_user(user):
    """Get client object from user, or None if not found"""
    try:
        return Client.objects.get(user=user)
    except Client.DoesNotExist:
        return None


# ==================== PORTAL DASHBOARD ====================

@login_required
@client_required
def portal_dashboard(request):
    """
    Main dashboard for client portal
    Shows overview of vehicles, payments, documents
    """
    client = get_client_from_user(request.user)
    
    if not client:
        # Client record doesn't exist yet - create one or show error
        messages.warning(request, 'Your client profile is being set up. Please contact support if this persists.')
        return render(request, 'clients/portal/no_profile.html')
    
    # Get client's vehicles
    vehicles = ClientVehicle.objects.filter(
        client=client,
        is_active=True
    ).select_related('vehicle').order_by('-purchase_date')[:5]
    
    # Get active installment plans
    active_plans = InstallmentPlan.objects.filter(
        client_vehicle__client=client,
        is_active=True
    ).annotate(
        total_paid=Sum('client_vehicle__payments__amount'),
        remaining_balance=F('total_amount') - Sum('client_vehicle__payments__amount')
    )
    
    # Get upcoming payments
    upcoming_payments = PaymentSchedule.objects.filter(
        installment_plan__client_vehicle__client=client,
        is_paid=False,
        due_date__gte=timezone.now().date()
    ).select_related('installment_plan').order_by('due_date')[:5]
    
    # Get recent payments
    recent_payments = Payment.objects.filter(
        client_vehicle__client=client
    ).order_by('-payment_date')[:5]
    
    # Get documents count
    documents_count = ClientDocument.objects.filter(
        client=client
    ).count()
    
    # Get active insurance policies
    active_insurance = InsurancePolicy.objects.filter(
        client=client,
        status='active',
        end_date__gte=timezone.now().date()
    ).count()
    
    # Calculate statistics
    total_vehicles = vehicles.count()
    total_debt = sum(plan.remaining_balance or 0 for plan in active_plans)
    overdue_payments = PaymentSchedule.objects.filter(
        installment_plan__client_vehicle__client=client,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    context = {
        'client': client,
        'vehicles': vehicles,
        'active_plans': active_plans,
        'upcoming_payments': upcoming_payments,
        'recent_payments': recent_payments,
        'total_vehicles': total_vehicles,
        'total_debt': total_debt,
        'overdue_payments': overdue_payments,
        'documents_count': documents_count,
        'active_insurance': active_insurance,
    }
    
    return render(request, 'clients/portal/dashboard.html', context)


# ==================== VEHICLES ====================

@login_required
@client_required
def portal_vehicles(request):
    """
    List all vehicles assigned to the client
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    vehicles = ClientVehicle.objects.filter(
        client=client
    ).select_related('vehicle').order_by('-purchase_date')
    
    context = {
        'client': client,
        'vehicles': vehicles,
    }
    
    return render(request, 'clients/portal/vehicles.html', context)


@login_required
@client_required
def portal_vehicle_detail(request, vehicle_id):
    """
    View details of a specific vehicle
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Ensure client can only view their own vehicles
    vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('vehicle'),
        client=client,
        id=vehicle_id
    )
    
    # Get related payments for this vehicle
    payments = Payment.objects.filter(
        client_vehicle=vehicle
    ).order_by('-payment_date')
    
    # Get installment plan for this vehicle
    installment_plan = InstallmentPlan.objects.filter(
        client_vehicle=vehicle
    ).first()
    
    # Get insurance for this vehicle
    insurance = InsurancePolicy.objects.filter(
        client=client,
        vehicle=vehicle.vehicle
    ).order_by('-start_date').first()
    
    context = {
        'client': client,
        'vehicle': vehicle,
        'payments': payments,
        'installment_plan': installment_plan,
        'insurance': insurance,
    }
    
    return render(request, 'clients/portal/vehicle_detail.html', context)


# ==================== PAYMENTS ====================

@login_required
@client_required
def portal_payments(request):
    """
    View all payments and payment schedules
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all payments
    payments = Payment.objects.filter(
        client_vehicle__client=client
    ).select_related('client_vehicle__vehicle').order_by('-payment_date')
    
    # Pagination
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate totals
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'total_paid': total_paid,
    }
    
    return render(request, 'clients/portal/payments.html', context)


@login_required
@client_required
def portal_payment_schedules(request):
    """
    View payment schedules
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all payment schedules
    schedules = PaymentSchedule.objects.filter(
        installment_plan__client_vehicle__client=client
    ).select_related('installment_plan', 'installment_plan__client_vehicle__vehicle').order_by('due_date')
    
    # Separate into upcoming, overdue, and paid
    today = timezone.now().date()
    upcoming = schedules.filter(is_paid=False, due_date__gte=today)
    overdue = schedules.filter(is_paid=False, due_date__lt=today)
    paid = schedules.filter(is_paid=True).order_by('-payment_date')[:10]
    
    context = {
        'client': client,
        'upcoming_schedules': upcoming,
        'overdue_schedules': overdue,
        'paid_schedules': paid,
    }
    
    return render(request, 'clients/portal/payment_schedules.html', context)


# ==================== INSTALLMENT PLANS ====================

@login_required
@client_required
def portal_installment_plans(request):
    """
    View all installment plans
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all installment plans
    plans = InstallmentPlan.objects.filter(
        client_vehicle__client=client
    ).select_related('client_vehicle__vehicle').annotate(
        total_paid=Sum('client_vehicle__payments__amount'),
        remaining_balance=F('total_amount') - Sum('client_vehicle__payments__amount')
    ).order_by('-start_date')
    
    context = {
        'client': client,
        'plans': plans,
    }
    
    return render(request, 'clients/portal/installment_plans.html', context)


@login_required
@client_required
def portal_installment_plan_detail(request, plan_id):
    """
    View details of a specific installment plan
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Ensure client can only view their own plans
    plan = get_object_or_404(
        InstallmentPlan.objects.select_related('vehicle'),
        client=client,
        id=plan_id
    )
    
    # Get payment schedules
    schedules = PaymentSchedule.objects.filter(
        installment_plan=plan
    ).order_by('due_date')
    
    # Get payments
    payments = Payment.objects.filter(
        installment_plan=plan
    ).order_by('-payment_date')
    
    # Calculate totals
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    remaining_balance = plan.total_amount - total_paid
    
    context = {
        'client': client,
        'plan': plan,
        'schedules': schedules,
        'payments': payments,
        'total_paid': total_paid,
        'remaining_balance': remaining_balance,
    }
    
    return render(request, 'clients/portal/installment_plan_detail.html', context)


# ==================== DOCUMENTS ====================

@login_required
@client_required
def portal_documents(request):
    """
    View all documents
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all documents
    documents = ClientDocument.objects.filter(
        client=client
    ).order_by('-uploaded_at')
    
    # Group by document type
    doc_types = documents.values('document_type').annotate(count=Count('id'))
    
    context = {
        'client': client,
        'documents': documents,
        'doc_types': doc_types,
    }
    
    return render(request, 'clients/portal/documents.html', context)


@login_required
@client_required
def portal_document_download(request, document_id):
    """
    Download a document
    """
    client = get_client_from_user(request.user)
    
    if not client:
        raise Http404("Client profile not found")
    
    # Ensure client can only download their own documents
    document = get_object_or_404(
        ClientDocument,
        client=client,
        id=document_id
    )
    
    if not document.file:
        messages.error(request, 'Document file not found.')
        return redirect('clients:portal_documents')
    
    # Serve the file
    try:
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.file.name.split('/')[-1]
        )
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('clients:portal_documents')


# ==================== INSURANCE ====================

@login_required
@client_required
def portal_insurance(request):
    """
    View all insurance policies
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all insurance policies
    policies = InsurancePolicy.objects.filter(
        client=client
    ).select_related('vehicle').order_by('-start_date')
    
    # Separate into active and expired
    today = timezone.now().date()
    active_policies = policies.filter(end_date__gte=today, status='active')
    expired_policies = policies.filter(Q(end_date__lt=today) | Q(status='expired'))
    
    context = {
        'client': client,
        'active_policies': active_policies,
        'expired_policies': expired_policies,
    }
    
    return render(request, 'clients/portal/insurance.html', context)


@login_required
@client_required
def portal_insurance_detail(request, insurance_id):
    """
    View details of a specific insurance policy
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Ensure client can only view their own insurance
    insurance = get_object_or_404(
        InsurancePolicy.objects.select_related('vehicle'),
        client=client,
        id=insurance_id
    )
    
    context = {
        'client': client,
        'insurance': insurance,
    }
    
    return render(request, 'clients/portal/insurance_detail.html', context)


# ==================== PROFILE ====================

@login_required
@client_required
def portal_profile(request):
    """
    View and edit client profile
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    if request.method == 'POST':
        # Handle profile update
        # This can be expanded with a form
        messages.info(request, 'Profile update functionality coming soon.')
        return redirect('clients:portal_profile')
    
    context = {
        'client': client,
    }
    
    return render(request, 'clients/portal/profile.html', context)


# ==================== NOTIFICATIONS ====================

@login_required
@client_required
def portal_notifications(request):
    """
    View all notifications
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # TODO: Implement notifications system
    context = {
        'client': client,
        'notifications': [],  # Placeholder
    }
    
    return render(request, 'clients/portal/notifications.html', context)


# ==================== VEHICLE MARKETPLACE ====================

@login_required
@client_required
def portal_marketplace(request):
    """
    View available vehicles for purchase
    Clients can browse and select vehicles to buy
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all available vehicles
    vehicles = Vehicle.objects.available().select_related('added_by')
    
    # Apply filters
    make = request.GET.get('make')
    body_type = request.GET.get('body_type')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    
    if make:
        vehicles = vehicles.filter(make__icontains=make)
    if body_type:
        vehicles = vehicles.filter(body_type=body_type)
    if min_price:
        vehicles = vehicles.filter(selling_price__gte=min_price)
    if max_price:
        vehicles = vehicles.filter(selling_price__lte=max_price)
    
    # Get unique makes and body types for filters
    makes = Vehicle.objects.available().values_list('make', flat=True).distinct()
    body_types = Vehicle.objects.available().values_list('body_type', flat=True).distinct()
    
    # Pagination
    paginator = Paginator(vehicles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'makes': makes,
        'body_types': body_types,
        'current_filters': {
            'make': make,
            'body_type': body_type,
            'min_price': min_price,
            'max_price': max_price,
        }
    }
    
    return render(request, 'clients/portal/marketplace.html', context)


@login_required
@client_required
def portal_vehicle_marketplace_detail(request, vehicle_id):
    """
    View details of an available vehicle and initiate purchase
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get vehicle - must be available
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status=VehicleStatus.AVAILABLE)
    
    # Check if client already has this vehicle
    already_purchased = ClientVehicle.objects.filter(
        client=client,
        vehicle=vehicle
    ).exists()
    
    context = {
        'client': client,
        'vehicle': vehicle,
        'already_purchased': already_purchased,
    }
    
    return render(request, 'clients/portal/marketplace_vehicle_detail.html', context)


@login_required
@client_required
def portal_initiate_purchase(request, vehicle_id):
    """
    Initiate vehicle purchase - choose payment plan
    Handles both returning clients and new users from public page
    """
    client = get_client_from_user(request.user)
    
    if not client:
        # If user doesn't have a client profile, create one
        messages.info(request, 'Setting up your client profile...')
        client = Client.objects.create(
            user=request.user,
            first_name=request.user.first_name,
            last_name=request.user.last_name,
            email=request.user.email,
            phone=request.user.phone if hasattr(request.user, 'phone') else '',
            is_active=True,
            created_by=request.user
        )
        messages.success(request, 'Your client profile has been created!')
    
    # Get vehicle
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status=VehicleStatus.AVAILABLE)
    
    # Check if already purchased
    if ClientVehicle.objects.filter(client=client, vehicle=vehicle).exists():
        messages.warning(request, 'You have already purchased this vehicle.')
        return redirect('clients:portal_vehicles')
    
    if request.method == 'POST':
        # Get form data
        down_payment = Decimal(request.POST.get('down_payment', '0'))
        payment_plan = request.POST.get('payment_plan')  # '6', '12', '24', 'full'
        
        # Validate down payment
        if down_payment < vehicle.deposit_required:
            messages.error(request, f'Minimum deposit required is KSH {vehicle.deposit_required:,.2f}')
            return redirect('clients:portal_initiate_purchase', vehicle_id=vehicle_id)
        
        if down_payment > vehicle.selling_price:
            messages.error(request, 'Down payment cannot exceed the vehicle price.')
            return redirect('clients:portal_initiate_purchase', vehicle_id=vehicle_id)
        
        # Create ClientVehicle
        client_vehicle = ClientVehicle.objects.create(
            client=client,
            vehicle=vehicle,
            purchase_price=vehicle.selling_price,
            deposit_paid=down_payment,
            total_paid=down_payment,  # Initialize total_paid with down_payment
            balance=vehicle.selling_price - down_payment,  # Calculate initial balance
            purchase_date=timezone.now().date(),
            is_active=True,
            created_by=request.user
        )
        
        # If full payment
        if payment_plan == 'full' or down_payment >= vehicle.selling_price:
            # Create payment record
            Payment.objects.create(
                client_vehicle=client_vehicle,
                amount=down_payment,
                payment_date=timezone.now().date(),
                payment_method='pending',  # Will be updated after actual payment
                notes='Initial down payment - pending confirmation',
                recorded_by=request.user
            )
            
            # Redirect to payment page
            return redirect('clients:portal_make_payment', client_vehicle_id=client_vehicle.id, payment_type='down_payment')
        
        # Create installment plan
        duration_months = int(payment_plan)
        balance = vehicle.selling_price - down_payment
        monthly_payment = balance / duration_months
        
        installment_plan = InstallmentPlan.objects.create(
            client_vehicle=client_vehicle,
            total_amount=vehicle.selling_price,
            deposit=down_payment,
            monthly_installment=monthly_payment,
            number_of_installments=duration_months,
            interest_rate=Decimal('0.00'),  # Can be configured
            start_date=timezone.now().date(),
            is_active=True,
            created_by=request.user
        )
        
        # Generate payment schedule
        installment_plan.generate_payment_schedule()
        
        # Redirect to payment page for down payment
        messages.success(request, 'Vehicle purchase initiated! Please complete your down payment.')
        return redirect('clients:portal_make_payment', client_vehicle_id=client_vehicle.id, payment_type='down_payment')
    
    # Calculate payment options
    selling_price = vehicle.selling_price
    min_deposit = vehicle.deposit_required
    
    payment_options = []
    for months in [6, 12, 24, 36]:
        balance = selling_price - min_deposit
        monthly = balance / months
        total_with_interest = balance * Decimal('1.05')  # 5% interest
        monthly_with_interest = total_with_interest / months
        
        payment_options.append({
            'months': months,
            'monthly_payment': monthly,
            'monthly_with_interest': monthly_with_interest,
            'total_interest': total_with_interest - balance,
            'total_amount': total_with_interest + min_deposit
        })
    
    context = {
        'client': client,
        'vehicle': vehicle,
        'payment_options': payment_options,
        'min_deposit': min_deposit,
    }
    
    return render(request, 'clients/portal/initiate_purchase.html', context)


@login_required
@client_required
def portal_make_payment(request, client_vehicle_id, payment_type='installment'):
    """
    Make a payment - choose payment method (M-Pesa, Bank Transfer, etc.)
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get client vehicle
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('vehicle', 'installment_plan'),
        id=client_vehicle_id,
        client=client
    )
    
    # Determine amount to pay
    if payment_type == 'down_payment':
        amount_to_pay = client_vehicle.deposit_paid
        description = 'Down Payment'
    elif payment_type == 'balance':
        # Full balance payment (when no installment plan)
        amount_to_pay = client_vehicle.balance
        description = 'Balance Payment'
        if amount_to_pay <= 0:
            messages.success(request, 'This vehicle is already fully paid!')
            return redirect('clients:portal_vehicle_detail', vehicle_id=client_vehicle.id)
    else:
        # Get next pending schedule
        next_schedule = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle=client_vehicle,
            is_paid=False
        ).order_by('due_date').first()
        
        if next_schedule:
            amount_to_pay = next_schedule.amount_due
            description = f'Installment #{next_schedule.installment_number}'
        else:
            messages.info(request, 'No pending payments found.')
            return redirect('clients:portal_vehicle_detail', vehicle_id=client_vehicle.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'mpesa':
            phone_number = request.POST.get('phone_number')
            # Initiate M-Pesa STK Push
            # This will be implemented in the M-Pesa integration
            messages.info(request, 'M-Pesa STK Push initiated. Please check your phone to complete the payment.')
            # Store pending payment info in session
            request.session['pending_payment'] = {
                'client_vehicle_id': client_vehicle_id,
                'amount': str(amount_to_pay),
                'payment_type': payment_type,
                'phone_number': phone_number
            }
            return redirect('clients:portal_payment_pending')
        
        elif payment_method == 'bank_transfer':
            # Show bank details for transfer
            return redirect('clients:portal_payment_bank_details', client_vehicle_id=client_vehicle_id, payment_type=payment_type)
        
        elif payment_method == 'cash':
            messages.info(request, 'Please visit our office to make a cash payment.')
            return redirect('clients:portal_vehicle_detail', vehicle_id=client_vehicle.id)
    
    context = {
        'client': client,
        'client_vehicle': client_vehicle,
        'amount_to_pay': amount_to_pay,
        'description': description,
        'payment_type': payment_type,
    }
    
    return render(request, 'clients/portal/make_payment.html', context)


@login_required
@client_required
def portal_payment_pending(request):
    """
    Show pending payment status
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get pending payment info from session
    pending_payment = request.session.get('pending_payment')
    
    if not pending_payment:
        messages.warning(request, 'No pending payment found.')
        return redirect('clients:portal_dashboard')
    
    context = {
        'client': client,
        'pending_payment': pending_payment,
    }
    
    return render(request, 'clients/portal/payment_pending.html', context)


@login_required
@client_required
def portal_payment_bank_details(request, client_vehicle_id, payment_type):
    """
    Show bank details for manual transfer
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('vehicle'),
        id=client_vehicle_id,
        client=client
    )
    
    # Determine amount
    if payment_type == 'down_payment':
        amount_to_pay = client_vehicle.deposit_paid
    elif payment_type == 'balance':
        amount_to_pay = client_vehicle.balance
    else:
        next_schedule = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle=client_vehicle,
            is_paid=False
        ).order_by('due_date').first()
        amount_to_pay = next_schedule.amount_due if next_schedule else Decimal('0')
    
    # Bank details (should be from settings/config)
    bank_details = {
        'bank_name': 'Example Bank Limited',
        'account_name': 'Vehicle Management System',
        'account_number': '1234567890',
        'branch': 'Main Branch',
        'swift_code': 'EXAMPLEKE',
    }
    
    context = {
        'client': client,
        'client_vehicle': client_vehicle,
        'amount_to_pay': amount_to_pay,
        'payment_type': payment_type,
        'bank_details': bank_details,
    }
    
    return render(request, 'clients/portal/payment_bank_details.html', context)


# ==================== VEHICLE REMOVAL ====================

@login_required
@client_required
def portal_remove_vehicle(request, vehicle_id):
    """
    Allow clients to remove a vehicle from their profile
    This is used when a client decides not to continue with a vehicle purchase
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get the client vehicle - ensure it belongs to the client
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('vehicle'),
        id=vehicle_id,
        client=client
    )
    
    # Check if vehicle is already fully paid
    if client_vehicle.is_paid_off:
        messages.warning(request, 'This vehicle is fully paid and cannot be removed. Please contact support for assistance.')
        return redirect('clients:portal_vehicle_detail', vehicle_id=client_vehicle.id)
    
    if request.method == 'POST':
        # Confirm removal
        confirmation = request.POST.get('confirm_removal')
        removal_reason = request.POST.get('removal_reason', '')
        
        if confirmation == 'yes':
            # Store vehicle info for the message
            vehicle_name = f"{client_vehicle.vehicle.year} {client_vehicle.vehicle.make} {client_vehicle.vehicle.model}"
            
            # Get associated installment plan if exists
            installment_plan = InstallmentPlan.objects.filter(
                client_vehicle=client_vehicle
            ).first()
            
            # Deactivate the installment plan
            if installment_plan:
                installment_plan.is_active = False
                installment_plan.save()
                
                # Mark all pending payment schedules as cancelled
                PaymentSchedule.objects.filter(
                    installment_plan=installment_plan,
                    is_paid=False
                ).update(is_paid=False)  # Keep them as unpaid but plan is inactive
            
            # Update the vehicle status back to available if no payments made
            # or keep as is if some payments were made (for accounting purposes)
            if client_vehicle.total_paid == Decimal('0.00'):
                # No payments made, return vehicle to available
                vehicle = client_vehicle.vehicle
                vehicle.status = VehicleStatus.AVAILABLE
                vehicle.save()
            
            # Mark the client vehicle as inactive instead of deleting
            # This preserves the record for auditing purposes
            client_vehicle.is_active = False
            client_vehicle.notes = f"Vehicle removed by client. Reason: {removal_reason or 'Not specified'}"
            client_vehicle.save()
            
            # Update client's current debt
            client.current_debt -= client_vehicle.balance
            if client.current_debt < 0:
                client.current_debt = Decimal('0.00')
            client.save()
            
            # Create an audit log entry if audit app is available
            try:
                from apps.audit.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='vehicle_removal',
                    model_name='ClientVehicle',
                    object_id=client_vehicle.id,
                    description=f"Client removed vehicle: {vehicle_name}. Reason: {removal_reason or 'Not specified'}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            except ImportError:
                pass  # Audit app not available
            
            messages.success(
                request, 
                f'Vehicle "{vehicle_name}" has been removed from your profile. '
                f'Any payments made will be processed for refund by our team. '
                f'We will contact you shortly regarding the next steps.'
            )
            return redirect('clients:portal_vehicles')
        else:
            messages.error(request, 'Please confirm that you want to remove this vehicle.')
            return redirect('clients:portal_remove_vehicle', vehicle_id=client_vehicle.id)
    
    # GET request - show confirmation page
    # Calculate what client stands to lose
    amount_paid = client_vehicle.total_paid
    balance_remaining = client_vehicle.balance
    
    # Get payment count
    payment_count = Payment.objects.filter(
        client_vehicle=client_vehicle
    ).count()
    
    # Get installment plan details
    installment_plan = InstallmentPlan.objects.filter(
        client_vehicle=client_vehicle
    ).first()
    
    context = {
        'client': client,
        'client_vehicle': client_vehicle,
        'amount_paid': amount_paid,
        'balance_remaining': balance_remaining,
        'payment_count': payment_count,
        'installment_plan': installment_plan,
    }
    
    return render(request, 'clients/portal/remove_vehicle.html', context)


# ==================== AUCTIONS ====================

@login_required
@client_required
def portal_auctions(request):
    """
    View all active and upcoming auctions
    Clients can browse auction vehicles
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get active and scheduled auctions
    auctions = Auction.objects.filter(
        status__in=['active', 'scheduled']
    ).select_related('vehicle').annotate(
        bid_count=Count('bids'),
        max_bid=Max('bids__bid_amount')
    ).order_by('end_date')
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        auctions = auctions.filter(status=status)
    
    search = request.GET.get('search')
    if search:
        auctions = auctions.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(vehicle__make__icontains=search) |
            Q(vehicle__model__icontains=search)
        )
    
    min_price = request.GET.get('min_price')
    if min_price:
        auctions = auctions.filter(starting_price__gte=Decimal(min_price))
    
    max_price = request.GET.get('max_price')
    if max_price:
        auctions = auctions.filter(starting_price__lte=Decimal(max_price))
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(auctions, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user's watchlist
    watchlist_ids = AuctionWatchlist.objects.filter(
        user=request.user
    ).values_list('auction_id', flat=True)
    
    # Get auctions user is participating in
    participating_ids = AuctionParticipant.objects.filter(
        user=request.user,
        is_approved=True
    ).values_list('auction_id', flat=True)
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'watchlist_ids': list(watchlist_ids),
        'participating_ids': list(participating_ids),
        'active_count': Auction.objects.filter(status='active').count(),
        'upcoming_count': Auction.objects.filter(status='scheduled').count(),
    }
    
    return render(request, 'clients/portal/auctions.html', context)


@login_required
@client_required
def portal_auction_detail(request, auction_id):
    """
    View details of a specific auction
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get auction
    auction = get_object_or_404(
        Auction.objects.select_related('vehicle'),
        id=auction_id
    )
    
    # Increment view count
    auction.views_count += 1
    auction.save(update_fields=['views_count'])
    
    # Get recent bids
    recent_bids = auction.bids.select_related('bidder').order_by('-created_at')[:10]
    
    # Check if user is registered for this auction
    is_registered = AuctionParticipant.objects.filter(
        auction=auction,
        user=request.user,
        is_approved=True
    ).exists()
    
    # Check if user is watching
    is_watching = AuctionWatchlist.objects.filter(
        auction=auction,
        user=request.user
    ).exists()
    
    # Get user's bids on this auction
    user_bids = auction.bids.filter(bidder=request.user).order_by('-created_at')[:5]
    
    # Check if user is highest bidder
    highest_bid = auction.bids.filter(is_active=True).order_by('-bid_amount').first()
    is_highest_bidder = highest_bid and highest_bid.bidder == request.user if highest_bid else False
    
    # Calculate minimum bid
    min_bid = auction.current_bid + auction.bid_increment if auction.current_bid > 0 else auction.starting_price
    
    # Get statistics
    total_participants = auction.participants.filter(is_approved=True).count()
    average_bid = auction.bids.aggregate(avg=Avg('bid_amount'))['avg'] or Decimal('0')
    
    context = {
        'client': client,
        'auction': auction,
        'recent_bids': recent_bids,
        'is_registered': is_registered,
        'is_watching': is_watching,
        'user_bids': user_bids,
        'is_highest_bidder': is_highest_bidder,
        'min_bid': min_bid,
        'total_participants': total_participants,
        'average_bid': average_bid,
        'highest_bid': highest_bid,
    }
    
    return render(request, 'clients/portal/auction_detail.html', context)


@login_required
@client_required
def portal_place_bid(request, auction_id):
    """
    Place a bid on an auction
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    if not auction.is_active:
        messages.error(request, 'This auction is not active.')
        return redirect('clients:portal_auction_detail', auction_id=auction_id)
    
    # Check if user is registered (if required)
    if auction.require_registration:
        is_registered = AuctionParticipant.objects.filter(
            auction=auction,
            user=request.user,
            is_approved=True
        ).exists()
        
        if not is_registered:
            messages.error(request, 'You must register for this auction before bidding.')
            return redirect('clients:portal_register_auction', auction_id=auction_id)
    
    if request.method == 'POST':
        bid_amount = Decimal(request.POST.get('bid_amount', '0'))
        
        # Validate bid
        can_bid, message = auction.can_place_bid(request.user, bid_amount)
        
        if not can_bid:
            messages.error(request, message)
            return redirect('clients:portal_auction_detail', auction_id=auction_id)
        
        # Create bid
        bid = Bid.objects.create(
            auction=auction,
            bidder=request.user,
            bid_amount=bid_amount,
            bid_type='manual',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        messages.success(request, f'Bid of KSH {bid_amount:,.2f} placed successfully!')
        
        # Check if auction should be extended
        time_remaining = auction.time_remaining
        if time_remaining and time_remaining.total_seconds() < 300:  # Less than 5 minutes
            auction.extend_auction()
            messages.info(request, 'Auction extended by 5 minutes due to late bid.')
        
        return redirect('clients:portal_auction_detail', auction_id=auction_id)
    
    # GET request - show bid form
    min_bid = auction.current_bid + auction.bid_increment if auction.current_bid > 0 else auction.starting_price
    
    context = {
        'client': client,
        'auction': auction,
        'min_bid': min_bid,
    }
    
    return render(request, 'clients/portal/place_bid.html', context)


@login_required
@client_required
def portal_register_auction(request, auction_id):
    """
    Register to participate in an auction
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    # Check if already registered
    existing = AuctionParticipant.objects.filter(
        auction=auction,
        user=request.user
    ).first()
    
    if existing:
        if existing.is_approved:
            messages.info(request, 'You are already registered for this auction.')
        else:
            messages.info(request, 'Your registration is pending approval.')
        return redirect('clients:portal_auction_detail', auction_id=auction_id)
    
    if request.method == 'POST':
        # Get client profile if not exists
        if not client:
            client = Client.objects.filter(user=request.user).first()
        
        # Create participant registration
        participant = AuctionParticipant.objects.create(
            auction=auction,
            user=request.user,
            client=client,
            is_approved=not auction.require_registration,  # Auto-approve if registration not required
            email_notifications=request.POST.get('email_notifications', 'on') == 'on',
            sms_notifications=request.POST.get('sms_notifications', 'off') == 'on'
        )
        
        if auction.require_registration:
            messages.success(request, 'Registration submitted successfully. Awaiting approval.')
        else:
            messages.success(request, 'You are now registered for this auction!')
        
        return redirect('clients:portal_auction_detail', auction_id=auction_id)
    
    context = {
        'client': client,
        'auction': auction,
    }
    
    return render(request, 'clients/portal/register_auction.html', context)


@login_required
@client_required
def portal_add_to_watchlist(request, auction_id):
    """
    Add auction to watchlist
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    watchlist, created = AuctionWatchlist.objects.get_or_create(
        auction=auction,
        user=request.user,
        defaults={
            'notify_before_end': True,
            'notify_on_outbid': True
        }
    )
    
    if created:
        auction.watchers_count += 1
        auction.save(update_fields=['watchers_count'])
        messages.success(request, 'Auction added to your watchlist.')
    else:
        messages.info(request, 'This auction is already in your watchlist.')
    
    return redirect('clients:portal_auction_detail', auction_id=auction_id)


@login_required
@client_required
def portal_remove_from_watchlist(request, auction_id):
    """
    Remove auction from watchlist
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    deleted_count = AuctionWatchlist.objects.filter(
        auction=auction,
        user=request.user
    ).delete()[0]
    
    if deleted_count:
        auction.watchers_count = max(0, auction.watchers_count - 1)
        auction.save(update_fields=['watchers_count'])
        messages.success(request, 'Auction removed from your watchlist.')
    
    return redirect('clients:portal_auction_detail', auction_id=auction_id)


@login_required
@client_required
def portal_my_bids(request):
    """
    View client's bidding history
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get all bids by the user
    bids = Bid.objects.filter(
        bidder=request.user
    ).select_related('auction', 'auction__vehicle').order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(bids, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_bids = bids.count()
    active_bids = bids.filter(auction__status='active').count()
    winning_bids = bids.filter(is_winning_bid=True).count()
    total_amount_bid = bids.aggregate(total=Sum('bid_amount'))['total'] or Decimal('0')
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'total_bids': total_bids,
        'active_bids': active_bids,
        'winning_bids': winning_bids,
        'total_amount_bid': total_amount_bid,
    }
    
    return render(request, 'clients/portal/my_bids.html', context)


@login_required
@client_required
def portal_my_watchlist(request):
    """
    View client's auction watchlist
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
    # Get watchlist
    watchlist = AuctionWatchlist.objects.filter(
        user=request.user
    ).select_related('auction', 'auction__vehicle').order_by('-added_at')
    
    context = {
        'client': client,
        'watchlist': watchlist,
    }
    
    return render(request, 'clients/portal/watchlist.html', context)
