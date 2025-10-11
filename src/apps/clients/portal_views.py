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
from apps.insurance.models import Insurance
from utils.constants import UserRole


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
    ).select_related('vehicle').order_by('-date_assigned')[:5]
    
    # Get active installment plans
    active_plans = InstallmentPlan.objects.filter(
        client=client,
        is_active=True
    ).annotate(
        total_paid=Sum('payment__amount'),
        remaining_balance=F('total_amount') - Sum('payment__amount')
    )
    
    # Get upcoming payments
    upcoming_payments = PaymentSchedule.objects.filter(
        installment_plan__client=client,
        is_paid=False,
        due_date__gte=timezone.now().date()
    ).select_related('installment_plan').order_by('due_date')[:5]
    
    # Get recent payments
    recent_payments = Payment.objects.filter(
        client=client
    ).order_by('-payment_date')[:5]
    
    # Get documents count
    documents_count = ClientDocument.objects.filter(
        client=client
    ).count()
    
    # Get active insurance policies
    active_insurance = Insurance.objects.filter(
        client=client,
        status='active',
        expiry_date__gte=timezone.now().date()
    ).count()
    
    # Calculate statistics
    total_vehicles = vehicles.count()
    total_debt = sum(plan.remaining_balance or 0 for plan in active_plans)
    overdue_payments = PaymentSchedule.objects.filter(
        installment_plan__client=client,
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
    ).select_related('vehicle').order_by('-date_assigned')
    
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
        client=client,
        vehicle=vehicle.vehicle
    ).order_by('-payment_date')
    
    # Get installment plan for this vehicle
    installment_plan = InstallmentPlan.objects.filter(
        client=client,
        vehicle=vehicle.vehicle
    ).first()
    
    # Get documents for this vehicle
    documents = ClientDocument.objects.filter(
        client=client,
        vehicle=vehicle.vehicle
    ).order_by('-uploaded_at')
    
    # Get insurance for this vehicle
    insurance = Insurance.objects.filter(
        client=client,
        vehicle=vehicle.vehicle
    ).order_by('-start_date').first()
    
    context = {
        'client': client,
        'vehicle': vehicle,
        'payments': payments,
        'installment_plan': installment_plan,
        'documents': documents,
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
        client=client
    ).select_related('vehicle', 'installment_plan').order_by('-payment_date')
    
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
        installment_plan__client=client
    ).select_related('installment_plan', 'installment_plan__vehicle').order_by('due_date')
    
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
        client=client
    ).select_related('vehicle').annotate(
        total_paid=Sum('payment__amount'),
        remaining_balance=F('total_amount') - Sum('payment__amount')
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
    ).select_related('vehicle').order_by('-uploaded_at')
    
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
    
    if not document.document_file:
        messages.error(request, 'Document file not found.')
        return redirect('clients:portal_documents')
    
    # Serve the file
    try:
        return FileResponse(
            document.document_file.open('rb'),
            as_attachment=True,
            filename=document.document_file.name.split('/')[-1]
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
    policies = Insurance.objects.filter(
        client=client
    ).select_related('vehicle').order_by('-start_date')
    
    # Separate into active and expired
    today = timezone.now().date()
    active_policies = policies.filter(expiry_date__gte=today, status='active')
    expired_policies = policies.filter(Q(expiry_date__lt=today) | Q(status='expired'))
    
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
        Insurance.objects.select_related('vehicle'),
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
