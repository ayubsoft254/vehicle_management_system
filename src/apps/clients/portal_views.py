"""
Client Portal Views
Views for client-facing portal where clients can manage their accounts
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Prefetch, F
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
    """
    client = get_client_from_user(request.user)
    
    if not client:
        messages.error(request, 'Client profile not found.')
        return redirect('clients:portal_dashboard')
    
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
