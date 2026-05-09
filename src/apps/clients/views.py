"""
Views for the client app
Handles client management, vehicle assignments, payments, and documents
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.db import models, transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
from decimal import Decimal

from .models import Client, ClientVehicle, ClientDocument
from apps.payments.models import Payment, InstallmentPlan
from .forms import (
    ClientForm, ClientVehicleForm, PaymentForm, 
    ClientDocumentForm, ClientSearchForm, InstallmentPlanForm
)
from apps.vehicles.models import Vehicle
from apps.audit.utils import log_audit


# ==================== CLIENT MANAGEMENT VIEWS ====================

@login_required
def client_list(request):
    """
    Display list of all clients with search and filtering
    """
    clients = Client.objects.all().order_by('-date_registered')
    
    # Search and filtering
    search_form = ClientSearchForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        status = search_form.cleaned_data.get('status')
        id_type = search_form.cleaned_data.get('id_type')
        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')
        
        if search:
            clients = clients.filter(
                Q(first_name__icontains=search) |
                Q(middle_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(id_number__icontains=search) |
                Q(phone_primary__icontains=search) |
                Q(email__icontains=search)
            )
        
        if status:
            clients = clients.filter(status=status)
        
        if id_type:
            clients = clients.filter(id_type=id_type)
        
        if date_from:
            clients = clients.filter(date_registered__gte=date_from)
        
        if date_to:
            clients = clients.filter(date_registered__lte=date_to)
    
    # Statistics
    total_clients = clients.count()
    active_clients = clients.filter(status='active').count()
    defaulted_clients = clients.filter(status='defaulted').count()
    completed_clients = clients.filter(status='completed').count()
    
    # Pagination
    paginator = Paginator(clients, 20)  # 20 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'clients': page_obj,
        'search_form': search_form,
        'total_clients': total_clients,
        'active_clients': active_clients,
        'defaulted_clients': defaulted_clients,
        'completed_clients': completed_clients,
    }
    
    log_audit(request.user, 'view', 'Client', 'Viewed client list')
    
    return render(request, 'clients/client_list.html', context)


@login_required
def client_detail(request, pk):
    """
    Display detailed information about a specific client
    """
    client = get_object_or_404(Client, pk=pk)
    
    # Get client's vehicles with payment plans
    client_vehicles = ClientVehicle.objects.filter(client=client).select_related('vehicle')
    
    # Enrich vehicles with payment plan and schedule information
    vehicles_with_plans = []
    for cv in client_vehicles:
        vehicle_data = {
            'client_vehicle': cv,
            'installment_plan': None,
            'next_payment': None,
            'payment_schedule': None,
            'all_schedules': None,
        }
        
        # Get installment plan if it exists
        try:
            plan = InstallmentPlan.objects.get(client_vehicle=cv)
            vehicle_data['installment_plan'] = plan
            
            # Get ALL payment schedules for the full breakdown table
            from apps.payments.models import PaymentSchedule
            all_schedules = PaymentSchedule.objects.filter(
                installment_plan=plan
            ).order_by('installment_number')
            vehicle_data['all_schedules'] = all_schedules
            
            # Get upcoming payment schedule (next 5)
            payment_schedule = all_schedules.filter(is_paid=False)[:5]
            vehicle_data['payment_schedule'] = payment_schedule
            
            # Get next payment
            next_payment = all_schedules.filter(is_paid=False).order_by('due_date').first()
            vehicle_data['next_payment'] = next_payment
        except InstallmentPlan.DoesNotExist:
            pass
        
        vehicles_with_plans.append(vehicle_data)
    
    # Get client's payments
    payments = Payment.objects.filter(
        client_vehicle__client=client
    ).order_by('-payment_date')[:10]
    
    # Get client's documents
    documents = ClientDocument.objects.filter(client=client).order_by('-uploaded_at')
    
    # Calculate statistics
    total_purchases = client_vehicles.count()
    total_spent = client_vehicles.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
    total_paid = client_vehicles.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
    total_balance = client_vehicles.aggregate(Sum('balance'))['balance__sum'] or 0
    
    # Recent activity
    recent_payments = payments[:5]
    
    context = {
        'client': client,
        'client_vehicles': client_vehicles,
        'vehicles_with_plans': vehicles_with_plans,
        'payments': payments,
        'documents': documents,
        'total_purchases': total_purchases,
        'total_spent': total_spent,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'recent_payments': recent_payments,
    }
    
    log_audit(request.user, 'view', 'Client', f'Viewed client: {client.get_full_name()}')
    
    return render(request, 'clients/client_detail.html', context)


@login_required
def client_create(request):
    """
    Create a new client
    """
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.registered_by = request.user
            client.save()
            
            log_audit(request.user, 'create', 'Client', f'Created client: {client.get_full_name()}')
            
            messages.success(request, f'Client {client.get_full_name()} created successfully!')
            return redirect('clients:client_detail', pk=client.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientForm()
    
    context = {
        'form': form,
        'title': 'Register New Client',
        'button_text': 'Register Client'
    }
    
    return render(request, 'clients/client_form.html', context)


@login_required
def client_update(request, pk):
    """
    Update existing client information
    """
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            
            log_audit(request.user, 'update', 'Client', f'Updated client: {client.get_full_name()}')
            
            messages.success(request, f'Client {client.get_full_name()} updated successfully!')
            return redirect('clients:client_detail', pk=client.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientForm(instance=client)
    
    context = {
        'form': form,
        'client': client,
        'title': f'Update Client: {client.get_full_name()}',
        'button_text': 'Update Client'
    }
    
    return render(request, 'clients/client_form.html', context)


@login_required
def client_delete(request, pk):
    """
    Delete a client (soft delete by marking as inactive)
    """
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        client_name = client.get_full_name()
        client.is_active = False
        client.save()
        
        log_audit(request.user, 'delete', 'Client', f'Deactivated client: {client_name}')
        
        messages.success(request, f'Client {client_name} has been deactivated.')
        return redirect('clients:client_list')
    
    context = {
        'client': client
    }
    
    return render(request, 'clients/client_confirm_delete.html', context)


# ==================== VEHICLE ASSIGNMENT VIEWS ====================

@login_required
def assign_vehicle(request, client_pk):
    """
    Assign a vehicle to a client with insurance and multiple trackers
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    if request.method == 'POST':
        form = ClientVehicleForm(request.POST, client=client)
        if form.is_valid():
            with transaction.atomic():
                client_vehicle = form.save(commit=False)
                client_vehicle.client = client
                client_vehicle.created_by = request.user
                
                # Calculate balance
                client_vehicle.balance = (
                    client_vehicle.purchase_price - client_vehicle.deposit_paid
                )
                client_vehicle.total_paid = client_vehicle.deposit_paid
                
                client_vehicle.save()
                
                # Update vehicle status
                vehicle = client_vehicle.vehicle
                vehicle.status = 'sold'
                vehicle.save()
                
                # Update client status
                client.status = 'active'
                client.save()
                
                # Create Installment Plan based on payment type
                # Only create plan if payment_type is 'installment' or 'flexible' (not 'full')
                if client_vehicle.balance > 0 and client_vehicle.payment_type in ['installment', 'flexible']:
                    from apps.payments.models import InstallmentPlan
                    plan = InstallmentPlan.objects.create(
                        client_vehicle=client_vehicle,
                        total_amount=client_vehicle.purchase_price,
                        deposit=client_vehicle.deposit_paid,
                        monthly_installment=client_vehicle.monthly_installment,
                        number_of_installments=client_vehicle.installment_months,
                        start_date=timezone.now().date(),
                        is_active=True,
                        created_by=request.user
                    )
                
                # --- Handle Insurance ---
                insurance_provider_id = request.POST.get('insurance_provider_id')
                insurance_policy_number = request.POST.get('insurance_policy_number', '').strip()
                insurance_policy_type = request.POST.get('insurance_policy_type', 'comprehensive')
                insurance_start_date = request.POST.get('insurance_start_date', '').strip()
                insurance_end_date = request.POST.get('insurance_end_date', '').strip()
                insurance_premium = request.POST.get('insurance_premium', '').strip()
                insurance_buying_price = request.POST.get('insurance_buying_price', '').strip()
                insurance_selling_price = request.POST.get('insurance_selling_price', '').strip()
                insurance_agent_name = request.POST.get('insurance_agent_name', '').strip()
                insurance_agent_id = request.POST.get('insurance_agent_id', '').strip()
                insurance_has_plan = request.POST.get('insurance_has_payment_plan') == 'on'
                insurance_deposit = request.POST.get('insurance_deposit', '').strip()
                insurance_first_date = request.POST.get('insurance_first_payment_date', '').strip()
                insurance_last_date = request.POST.get('insurance_last_payment_date', '').strip()
                insurance_interest_rate = request.POST.get('insurance_interest_rate', '0').strip()
                
                if insurance_provider_id and insurance_policy_number and insurance_start_date and insurance_end_date:
                    try:
                        from apps.insurance.models import InsuranceProvider, InsurancePolicy
                        from datetime import datetime as dt
                        
                        provider = InsuranceProvider.objects.get(pk=insurance_provider_id)
                        
                        # Calculate insurance installment months from date range
                        insurance_months = None
                        if insurance_has_plan and insurance_first_date and insurance_last_date:
                            first = dt.strptime(insurance_first_date, '%Y-%m-%d').date()
                            last = dt.strptime(insurance_last_date, '%Y-%m-%d').date()
                            # Calculate months between dates
                            months_diff = (last.year - first.year) * 12 + (last.month - first.month)
                            insurance_months = max(1, months_diff)
                        
                        # Calculate monthly installment
                        insurance_monthly = None
                        if insurance_has_plan and insurance_selling_price:
                            selling = Decimal(insurance_selling_price or '0')
                            deposit = Decimal(insurance_deposit or '0')
                            balance = selling - deposit
                            rate = Decimal(insurance_interest_rate or '0')
                            
                            if insurance_months and insurance_months > 0:
                                total_with_interest = balance
                                if rate > 0:
                                    interest = balance * (rate / 100) * (insurance_months / 12)
                                    total_with_interest = balance + interest
                                insurance_monthly = total_with_interest / insurance_months
                        
                        InsurancePolicy.objects.create(
                            vehicle=vehicle,
                            provider=provider,
                            client=client,
                            policy_number=insurance_policy_number,
                            policy_type=insurance_policy_type,
                            start_date=insurance_start_date,
                            end_date=insurance_end_date,
                            premium_amount=Decimal(insurance_premium or '0'),
                            sum_insured=client_vehicle.purchase_price,
                            buying_price=Decimal(insurance_buying_price or '0'),
                            selling_price=Decimal(insurance_selling_price or '0'),
                            agent_name=insurance_agent_name,
                            agent_id=insurance_agent_id,
                            has_payment_plan=insurance_has_plan,
                            insurance_deposit=Decimal(insurance_deposit or '0') if insurance_has_plan else Decimal('0'),
                            insurance_installment_months=insurance_months if insurance_has_plan else None,
                            insurance_monthly_installment=insurance_monthly if insurance_has_plan else None,
                            insurance_interest_rate=Decimal(insurance_interest_rate or '0') if insurance_has_plan else Decimal('0'),
                            status='active',
                            created_by=request.user,
                        )
                    except Exception as e:
                        messages.warning(request, f'Vehicle assigned but insurance could not be saved: {e}')
                
                # --- Handle Multiple Trackers ---
                tracker_names = request.POST.getlist('tracker_name[]')
                tracker_serials = request.POST.getlist('tracker_serial[]')
                tracker_providers = request.POST.getlist('tracker_provider[]')
                tracker_install_dates = request.POST.getlist('tracker_install_date[]')
                tracker_buying_prices = request.POST.getlist('tracker_buying_price[]')
                tracker_selling_prices = request.POST.getlist('tracker_selling_price[]')
                tracker_has_plans = request.POST.getlist('tracker_has_plan[]')
                tracker_deposits = request.POST.getlist('tracker_deposit[]')
                tracker_first_dates = request.POST.getlist('tracker_first_payment_date[]')
                tracker_last_dates = request.POST.getlist('tracker_last_payment_date[]')
                tracker_interest_rates = request.POST.getlist('tracker_interest_rate[]')
                
                for i, name in enumerate(tracker_names):
                    if name.strip():
                        try:
                            from apps.clients.models import VehicleTracker
                            from datetime import datetime as dt
                            
                            has_plan = tracker_has_plans[i] == 'on' if i < len(tracker_has_plans) else False
                            install_date = tracker_install_dates[i] if i < len(tracker_install_dates) and tracker_install_dates[i] else timezone.now().date()
                            
                            # Calculate tracker installment months from date range
                            tracker_months = None
                            if has_plan and i < len(tracker_first_dates) and i < len(tracker_last_dates):
                                first_date_str = tracker_first_dates[i] if tracker_first_dates[i] else None
                                last_date_str = tracker_last_dates[i] if tracker_last_dates[i] else None
                                if first_date_str and last_date_str:
                                    first = dt.strptime(first_date_str, '%Y-%m-%d').date()
                                    last = dt.strptime(last_date_str, '%Y-%m-%d').date()
                                    # Calculate months between dates
                                    months_diff = (last.year - first.year) * 12 + (last.month - first.month)
                                    tracker_months = max(1, months_diff)
                            
                            # Calculate monthly installment
                            tracker_monthly = None
                            if has_plan and i < len(tracker_selling_prices) and tracker_selling_prices[i]:
                                selling = Decimal(tracker_selling_prices[i] or '0')
                                deposit = Decimal(tracker_deposits[i] if i < len(tracker_deposits) else '0')
                                balance = selling - deposit
                                rate = Decimal(tracker_interest_rates[i] if i < len(tracker_interest_rates) else '0')
                                
                                if tracker_months and tracker_months > 0:
                                    total_with_interest = balance
                                    if rate > 0:
                                        interest = balance * (rate / 100) * (tracker_months / 12)
                                        total_with_interest = balance + interest
                                    tracker_monthly = total_with_interest / tracker_months
                            
                            VehicleTracker.objects.create(
                                client_vehicle=client_vehicle,
                                tracker_name=name,
                                serial_number=tracker_serials[i] if i < len(tracker_serials) else '',
                                provider=tracker_providers[i] if i < len(tracker_providers) else '',
                                buying_price=Decimal(tracker_buying_prices[i]) if i < len(tracker_buying_prices) and tracker_buying_prices[i] else Decimal('0'),
                                selling_price=Decimal(tracker_selling_prices[i]) if i < len(tracker_selling_prices) and tracker_selling_prices[i] else Decimal('0'),
                                has_payment_plan=has_plan,
                                deposit=Decimal(tracker_deposits[i]) if i < len(tracker_deposits) and tracker_deposits[i] and has_plan else Decimal('0'),
                                installment_months=tracker_months if has_plan else None,
                                monthly_installment=tracker_monthly if has_plan else None,
                                interest_rate=Decimal(tracker_interest_rates[i]) if i < len(tracker_interest_rates) and tracker_interest_rates[i] and has_plan else Decimal('0'),
                                installed_date=install_date,
                                created_by=request.user,
                            )
                        except Exception as e:
                            messages.warning(request, f'Tracker "{name}" could not be saved: {e}')
                
                log_audit(
                    request.user, 'create', 'ClientVehicle',
                    f'Assigned vehicle {vehicle} to client {client.get_full_name()} '
                    f'with payment type: {client_vehicle.get_payment_type_display()}'
                )
                
                messages.success(
                    request, 
                    f'Vehicle {vehicle} assigned to {client.get_full_name()} successfully!'
                )
                return redirect('clients:client_detail', pk=client.pk)
        else:
            print("Form errors:", form.errors)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientVehicleForm(client=client)
    
    # Get vehicle prices for JavaScript
    vehicles_qs = Vehicle.objects.filter(status='available')
    vehicle_prices = {v.id: float(v.selling_price) for v in vehicles_qs}
    vehicle_cost_prices = {v.id: float(v.purchase_price) for v in vehicles_qs}
    
    # Get insurance providers
    from apps.insurance.models import InsuranceProvider
    insurance_providers = InsuranceProvider.objects.filter(is_active=True).order_by('name')
    
    context = {
        'form': form,
        'client': client,
        'title': f'Assign Vehicle to {client.get_full_name()}',
        'button_text': 'Assign Vehicle',
        'vehicle_prices_json': json.dumps(vehicle_prices),
        'vehicle_cost_prices_json': json.dumps(vehicle_cost_prices),
        'insurance_providers': insurance_providers,
    }
    
    return render(request, 'clients/assign_vehicle.html', context)


@login_required
def client_vehicle_detail(request, pk):
    """
    Display details of a client's vehicle purchase
    """
    from apps.payments.models import PaymentSchedule
    from django.utils import timezone
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'), 
        pk=pk
    )
    
    # Get payment history
    payments = Payment.objects.filter(
        client_vehicle=client_vehicle
    ).order_by('-payment_date')
    
    # Get installment plan if exists
    try:
        installment_plan = InstallmentPlan.objects.get(client_vehicle=client_vehicle)
    except InstallmentPlan.DoesNotExist:
        installment_plan = None
    
    # Get payment schedule information
    next_payment = None
    total_paid_schedule = Decimal('0.00')
    total_remaining_schedule = Decimal('0.00')
    
    if installment_plan:
        # Get next unpaid installment
        next_payment = PaymentSchedule.objects.filter(
            installment_plan=installment_plan,
            is_paid=False
        ).order_by('due_date').first()
        
        # Calculate totals from payment schedule
        all_schedules = PaymentSchedule.objects.filter(installment_plan=installment_plan)
        total_paid_schedule = all_schedules.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal('0.00')
        
        total_remaining_schedule = all_schedules.filter(
            is_paid=False
        ).aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')
    
    context = {
        'client_vehicle': client_vehicle,
        'payments': payments,
        'installment_plan': installment_plan,
        'payment_progress': client_vehicle.payment_progress,
        'next_payment': next_payment,
        'total_paid_schedule': total_paid_schedule,
        'total_remaining_schedule': total_remaining_schedule,
    }
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Viewed vehicle purchase details for {client_vehicle.client.get_full_name()}'
    )
    
    return render(request, 'clients/client_vehicle_detail.html', context)


@login_required
def client_vehicle_update(request, pk):
    """
    Update client vehicle assignment details
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=pk)
    
    if request.method == 'POST':
        form = ClientVehicleForm(request.POST, instance=client_vehicle)
        if form.is_valid():
            client_vehicle = form.save()
            
            # Automatically create Installment Plan if there's a balance and payment terms are provided
            if client_vehicle.balance > 0 and client_vehicle.installment_months:
                from apps.payments.models import InstallmentPlan
                plan, created = InstallmentPlan.objects.get_or_create(
                    client_vehicle=client_vehicle,
                    defaults={
                        'total_amount': client_vehicle.purchase_price,
                        'deposit': client_vehicle.deposit_paid,
                        'monthly_installment': client_vehicle.monthly_installment,
                        'number_of_installments': client_vehicle.installment_months,
                        'interest_rate': client_vehicle.interest_rate or Decimal('0.00'),
                        'start_date': timezone.now().date(),
                        'is_active': True,
                        'created_by': request.user
                    }
                )
                
                # Update existing plan if it exists and hasn't started payments
                if not created and not plan.payment_schedules.filter(is_paid=True).exists():
                    plan.total_amount = client_vehicle.purchase_price
                    plan.deposit = client_vehicle.deposit_paid
                    plan.monthly_installment = client_vehicle.monthly_installment
                    plan.number_of_installments = client_vehicle.installment_months
                    plan.interest_rate = client_vehicle.interest_rate or Decimal('0.00')
                    plan.save()
                    # Re-generate schedules
                    plan.payment_schedules.all().delete()
                    plan.generate_payment_schedule()
            
            log_audit(
                request.user, 'update', 'ClientVehicle',
                f'Updated vehicle assignment for {client_vehicle.client.get_full_name()}'
            )
            
            messages.success(request, 'Vehicle assignment updated successfully!')
            return redirect('clients:client_vehicle_detail', pk=client_vehicle.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientVehicleForm(instance=client_vehicle)
    
    # Get vehicle prices for JavaScript (include the currently assigned vehicle)
    vehicles = Vehicle.objects.filter(Q(status='available') | Q(id=client_vehicle.vehicle.id))
    vehicle_prices = {v.id: float(v.selling_price) for v in vehicles}
    vehicle_cost_prices = {v.id: float(v.purchase_price) for v in vehicles}
    
    context = {
        'form': form,
        'client': client_vehicle.client,
        'client_vehicle': client_vehicle,
        'title': 'Update Vehicle Assignment',
        'button_text': 'Update Assignment',
        'vehicle_prices_json': json.dumps(vehicle_prices),
        'vehicle_cost_prices_json': json.dumps(vehicle_cost_prices)
    }
    
    return render(request, 'clients/assign_vehicle.html', context)


# ==================== PAYMENT VIEWS ====================

@login_required
def record_payment(request, client_vehicle_pk):
    """
    Record a payment for a client's vehicle
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=client_vehicle_pk)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, client_vehicle=client_vehicle)
        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.client_vehicle = client_vehicle
                payment.recorded_by = request.user
                payment.save()
                # Check if fully paid
                client_vehicle.refresh_from_db()
                if client_vehicle.is_paid_off:
                    messages.success(
                        request, 
                        f'Payment recorded! Vehicle fully paid off!'
                    )
                else:
                    messages.success(
                        request, 
                        f'Payment of KES {payment.amount:,.2f} recorded successfully!'
                    )
                
                log_audit(
                    request.user, 'create', 'Payment',
                    f'Recorded payment of KES {payment.amount:,.2f} for {client_vehicle.client.get_full_name()}'
                )
                
                return redirect('clients:client_vehicle_detail', pk=client_vehicle.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(initial={'client_vehicle': client_vehicle})
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'title': f'Record Payment for {client_vehicle.client.get_full_name()}',
        'button_text': 'Record Payment'
    }
    
    return render(request, 'clients/payment_form.html', context)


@login_required
def payment_list(request):
    """
    Display list of all payments
    """
    payments = Payment.objects.select_related(
        'client_vehicle__client', 
        'client_vehicle__vehicle',
        'recorded_by'
    ).order_by('-payment_date')
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    # Statistics
    total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    payment_count = payments.count()
    
    # Pagination
    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'payments': page_obj,
        'total_payments': total_payments,
        'payment_count': payment_count,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed payment list')
    
    return render(request, 'clients/payment_list.html', context)


@login_required
def payment_detail(request, pk):
    """
    Display payment details
    """
    payment = get_object_or_404(
        Payment.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'recorded_by'
        ),
        pk=pk
    )
    
    context = {
        'payment': payment
    }
    
    log_audit(request.user, 'view', 'Payment', f'Viewed payment #{payment.pk}')
    
    return render(request, 'clients/payment_detail.html', context)


# ==================== DOCUMENT VIEWS ====================

@login_required
def upload_document(request, client_pk):
    """
    Upload a document for a client
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    if request.method == 'POST':
        form = ClientDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.client = client
            document.uploaded_by = request.user
            document.save()
            
            log_audit(
                request.user, 'create', 'ClientDocument',
                f'Uploaded document for {client.get_full_name()}: {document.title}'
            )
            
            messages.success(request, f'Document "{document.title}" uploaded successfully!')
            return redirect('clients:client_detail', pk=client.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientDocumentForm()
    
    context = {
        'form': form,
        'client': client,
        'title': f'Upload Document for {client.get_full_name()}',
        'button_text': 'Upload Document'
    }
    
    return render(request, 'clients/document_form.html', context)


@login_required
def document_list(request, client_pk):
    """
    List all documents for a client
    """
    client = get_object_or_404(Client, pk=client_pk)
    documents = ClientDocument.objects.filter(client=client).order_by('-uploaded_at')
    
    context = {
        'client': client,
        'documents': documents
    }
    
    return render(request, 'clients/document_list.html', context)


@login_required
def document_delete(request, pk):
    """
    Delete a client document
    """
    document = get_object_or_404(ClientDocument, pk=pk)
    client = document.client
    
    if request.method == 'POST':
        document_title = document.title
        document.delete()
        
        log_audit(
            request.user, 'delete', 'ClientDocument',
            f'Deleted document: {document_title}'
        )
        
        messages.success(request, f'Document "{document_title}" deleted successfully!')
        return redirect('clients:client_detail', pk=client.pk)
    
    context = {
        'document': document
    }
    
    return render(request, 'clients/document_confirm_delete.html', context)


# ==================== INSTALLMENT PLAN VIEWS ====================

@login_required
def create_installment_plan(request, client_vehicle_pk):
    """
    Create an installment plan for a client's vehicle
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=client_vehicle_pk)
    
    # Check if plan already exists
    if InstallmentPlan.objects.filter(client_vehicle=client_vehicle).exists():
        messages.warning(request, 'An installment plan already exists for this vehicle.')
        return redirect('clients:client_vehicle_detail', pk=client_vehicle.pk)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST, client_vehicle=client_vehicle)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.client_vehicle = client_vehicle
            plan.total_amount = client_vehicle.purchase_price
            plan.deposit = client_vehicle.deposit_paid
            plan.created_by = request.user
            plan.save()
            
            log_audit(
                request.user, 'create', 'InstallmentPlan',
                f'Created installment plan for {client_vehicle.client.get_full_name()}'
            )
            
            messages.success(request, 'Installment plan created successfully!')
            return redirect('clients:client_vehicle_detail', pk=client_vehicle.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill form with client vehicle data
        initial_data = {
            'monthly_installment': client_vehicle.monthly_installment,
            'number_of_installments': client_vehicle.installment_months,
            'interest_rate': client_vehicle.interest_rate,
            'start_date': client_vehicle.purchase_date,
        }
        form = InstallmentPlanForm(initial=initial_data, client_vehicle=client_vehicle)
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'title': 'Create Installment Plan',
        'button_text': 'Create Plan'
    }
    
    return render(request, 'clients/installment_plan_form.html', context)


# ==================== REPORTING & EXPORT VIEWS ====================

@login_required
def client_statement(request, client_pk):
    """
    Generate client statement showing all transactions
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    # Get all client vehicles and payments
    client_vehicles = ClientVehicle.objects.filter(client=client).select_related('vehicle')
    payments = Payment.objects.filter(
        client_vehicle__client=client
    ).order_by('payment_date')
    
    # Calculate totals
    total_purchases = client_vehicles.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
    total_paid = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    total_balance = client_vehicles.aggregate(Sum('balance'))['balance__sum'] or 0
    
    context = {
        'client': client,
        'client_vehicles': client_vehicles,
        'payments': payments,
        'total_purchases': total_purchases,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }
    
    log_audit(request.user, 'view', 'Client', f'Generated statement for {client.get_full_name()}')
    
    return render(request, 'clients/client_statement.html', context)


@login_required
def export_clients_csv(request):
    """
    Export clients to CSV
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="clients_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Full Name', 'ID Type', 'ID Number', 
        'Phone', 'Email', 'Status', 'Credit Limit',
        'Available Credit', 'Date Registered'
    ])
    
    clients = Client.objects.all().order_by('-date_registered')
    
    for client in clients:
        writer.writerow([
            client.pk,
            client.get_full_name(),
            client.get_id_type_display(),
            client.id_number,
            client.phone_primary,
            client.email or '',
            client.get_status_display(),
            client.credit_limit,
            client.available_credit,
            client.date_registered.strftime('%Y-%m-%d')
        ])
    
    log_audit(request.user, 'export', 'Client', 'Exported clients to CSV')
    
    return response


@login_required
def defaulters_report(request):
    """
    Generate report of clients with overdue payments
    """
    # Get clients with overdue payments (simplified logic)
    defaulted_clients = Client.objects.filter(status='defaulted')
    
    context = {
        'defaulted_clients': defaulted_clients,
        'total_defaulters': defaulted_clients.count(),
    }
    
    log_audit(request.user, 'view', 'Client', 'Viewed defaulters report')
    
    return render(request, 'clients/defaulters_report.html', context)


# ==================== AJAX/API VIEWS ====================

@login_required
def client_search_api(request):
    """
    AJAX endpoint for client search
    """
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'clients': []})
    
    clients = Client.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(id_number__icontains=query) |
        Q(phone_primary__icontains=query)
    )[:10]
    
    data = {
        'clients': [
            {
                'id': client.pk,
                'name': client.get_full_name(),
                'id_number': client.id_number,
                'phone': client.phone_primary,
                'status': client.status
            }
            for client in clients
        ]
    }
    
    return JsonResponse(data)


@login_required
def client_stats_api(request, pk):
    """
    AJAX endpoint for client statistics
    """
    client = get_object_or_404(Client, pk=pk)
    
    client_vehicles = ClientVehicle.objects.filter(client=client)
    
    data = {
        'total_purchases': client_vehicles.count(),
        'total_spent': float(client_vehicles.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0),
        'total_paid': float(client_vehicles.aggregate(Sum('total_paid'))['total_paid__sum'] or 0),
        'total_balance': float(client_vehicles.aggregate(Sum('balance'))['balance__sum'] or 0),
        'available_credit': float(client.available_credit),
        'credit_utilization': float(client.credit_utilization),
    }
    
    return JsonResponse(data)