"""
Views for the client app
Handles client management, vehicle assignments, payments, and documents
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db import models, transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
from decimal import Decimal

from .models import Client, ClientVehicle, ClientDocument, VehicleTracker
from apps.payments.models import Payment, PaymentSplit, InstallmentPlan
from .forms import (
    ClientForm, ClientVehicleForm, PaymentForm, 
    ClientDocumentForm, ClientSearchForm, InstallmentPlanForm
)
from apps.vehicles.models import Vehicle
from apps.audit.utils import log_audit
from utils.constants import UserRole


# ==================== CLIENT MANAGEMENT VIEWS ====================

@login_required
def client_list(request):
    """
    Display list of all clients with search and filtering
    """
    clients = Client.objects.annotate(
        outstanding_debt=Coalesce(
            Sum('vehicles__balance', filter=Q(vehicles__is_paid_off=False)),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).order_by('-date_registered')
    
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
def tracker_management(request):
    """
    Manage vehicle trackers and monitor payment completion.
    """
    trackers = VehicleTracker.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle'
    ).order_by('-created_at')

    search = request.GET.get('search', '').strip()
    payment_status = request.GET.get('payment_status', '').strip()

    if search:
        trackers = trackers.filter(
            Q(tracker_name__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(certificate_number__icontains=search)
            | Q(provider__icontains=search)
            | Q(client_vehicle__client__first_name__icontains=search)
            | Q(client_vehicle__client__middle_name__icontains=search)
            | Q(client_vehicle__client__last_name__icontains=search)
            | Q(client_vehicle__vehicle__registration_number__icontains=search)
        )

    if payment_status == 'fully_paid':
        trackers = trackers.filter(balance__lte=Decimal('0.00'))
    elif payment_status == 'partial':
        trackers = trackers.filter(total_paid__gt=Decimal('0.00'), balance__gt=Decimal('0.00'))
    elif payment_status == 'unpaid':
        trackers = trackers.filter(total_paid__lte=Decimal('0.00'), balance__gt=Decimal('0.00'))

    all_trackers = VehicleTracker.objects.all()
    total_sold = all_trackers.count()
    fully_paid_count = all_trackers.filter(balance__lte=Decimal('0.00')).count()
    partially_paid_count = all_trackers.filter(total_paid__gt=Decimal('0.00'), balance__gt=Decimal('0.00')).count()
    unpaid_count = all_trackers.filter(total_paid__lte=Decimal('0.00'), balance__gt=Decimal('0.00')).count()

    totals = all_trackers.aggregate(
        sold_value=Sum('selling_price'),
        paid_value=Sum('total_paid'),
        balance_value=Sum('balance')
    )

    paginator = Paginator(trackers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for tracker in page_obj:
        if tracker.selling_price and tracker.selling_price > 0:
            progress = (tracker.total_paid / tracker.selling_price) * Decimal('100')
            tracker.payment_progress = min(Decimal('100.00'), progress)
        else:
            tracker.payment_progress = Decimal('0.00')

        if tracker.balance <= 0:
            tracker.payment_status_label = 'Fully Paid'
            tracker.payment_status_color = 'green'
        elif tracker.total_paid > 0:
            tracker.payment_status_label = 'Partially Paid'
            tracker.payment_status_color = 'yellow'
        else:
            tracker.payment_status_label = 'Unpaid'
            tracker.payment_status_color = 'red'

    context = {
        'trackers': page_obj,
        'search': search,
        'payment_status': payment_status,
        'total_sold': total_sold,
        'fully_paid_count': fully_paid_count,
        'partially_paid_count': partially_paid_count,
        'unpaid_count': unpaid_count,
        'total_sold_value': totals.get('sold_value') or Decimal('0.00'),
        'total_paid_value': totals.get('paid_value') or Decimal('0.00'),
        'total_balance_value': totals.get('balance_value') or Decimal('0.00'),
    }

    log_audit(request.user, 'view', 'VehicleTracker', 'Viewed tracker management dashboard')

    return render(request, 'clients/tracker_management.html', context)


def _upsert_insurance_policy(*, request, client, vehicle, client_vehicle, insurance_data, existing_policy=None):
    """Create or update the insurance policy linked to a client vehicle assignment."""
    insurance_provider_id = insurance_data.get('insurance_provider_id')
    insurance_policy_number = insurance_data.get('insurance_policy_number', '').strip()
    insurance_start_date = insurance_data.get('insurance_start_date', '').strip()
    insurance_end_date = insurance_data.get('insurance_end_date', '').strip()

    if not (insurance_provider_id and insurance_policy_number and insurance_start_date and insurance_end_date):
        return existing_policy

    from apps.insurance.models import InsuranceProvider, InsurancePolicy, InsurancePaymentSchedule
    from datetime import datetime as dt

    def parse_money(value):
        try:
            return Decimal(str(value).strip() or '0')
        except Exception:
            return Decimal('0.00')

    insurance_policy_type = insurance_data.get('insurance_policy_type', 'comprehensive')
    insurance_vehicle_usage = insurance_data.get('insurance_vehicle_usage', 'private').strip() or 'private'
    insurance_buying_price = insurance_data.get('insurance_buying_price', '').strip()
    insurance_selling_price = insurance_data.get('insurance_selling_price', '').strip()
    insurance_agent_name = insurance_data.get('insurance_agent_name', '').strip()
    insurance_agent_id = insurance_data.get('insurance_agent_id', '').strip()
    insurance_payment_type = insurance_data.get('insurance_payment_type', 'full').strip()
    insurance_flexible_json = insurance_data.get('insurance_flexible_installments_json', '[]')
    insurance_has_plan = insurance_payment_type == 'flexible'

    provider = InsuranceProvider.objects.get(pk=insurance_provider_id)

    try:
        ins_installments = json.loads(insurance_flexible_json or '[]')
    except Exception:
        ins_installments = []

    insurance_months = None
    insurance_monthly = None
    insurance_deposit = Decimal('0.00')
    insurance_total_paid = Decimal('0.00')
    insurance_balance = parse_money(insurance_selling_price)

    if insurance_payment_type == 'deduct_from_deposit':
        insurance_deposit = min(client_vehicle.deposit_paid, parse_money(insurance_selling_price))
        insurance_total_paid = insurance_deposit
        insurance_balance = max(Decimal('0.00'), parse_money(insurance_selling_price) - insurance_deposit)
        insurance_has_plan = False
    elif insurance_has_plan and ins_installments:
        insurance_months = len(ins_installments)
        total_ins = sum((Decimal(str(row.get('amount', '0') or '0')) for row in ins_installments), Decimal('0.00'))
        insurance_monthly = (total_ins / insurance_months).quantize(Decimal('0.01')) if insurance_months else None

    policy = existing_policy or InsurancePolicy(
        vehicle=vehicle,
        client=client,
        created_by=request.user,
    )
    policy.vehicle = vehicle
    policy.provider = provider
    policy.client = client
    policy.policy_number = insurance_policy_number
    policy.policy_type = insurance_policy_type
    policy.vehicle_usage = insurance_vehicle_usage
    policy.start_date = insurance_start_date
    policy.end_date = insurance_end_date
    policy.premium_amount = parse_money(insurance_selling_price)
    policy.sum_insured = client_vehicle.purchase_price
    policy.buying_price = parse_money(insurance_buying_price)
    policy.selling_price = parse_money(insurance_selling_price)
    policy.agent_name = insurance_agent_name
    policy.agent_id = insurance_agent_id
    policy.payment_type = insurance_payment_type
    policy.has_payment_plan = insurance_has_plan
    policy.insurance_deposit = insurance_deposit
    policy.insurance_installment_months = insurance_months if insurance_has_plan else None
    policy.insurance_monthly_installment = insurance_monthly if insurance_has_plan else None
    policy.insurance_total_paid = insurance_total_paid
    policy.insurance_balance = insurance_balance
    policy.insurance_interest_rate = Decimal('0.00')
    policy.status = 'active'
    policy.save()

    policy.insurance_payment_schedules.all().delete()
    if insurance_has_plan and ins_installments:
        for idx, installment in enumerate(ins_installments, start=1):
            due_date = dt.strptime(str(installment.get('due_date')).strip(), '%Y-%m-%d').date()
            amount_due = Decimal(str(installment.get('amount')).strip())
            InsurancePaymentSchedule.objects.create(
                policy=policy,
                installment_number=idx,
                due_date=due_date,
                amount_due=amount_due,
            )

    return policy


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

                def parse_money(value):
                    try:
                        return Decimal(str(value).strip() or '0')
                    except Exception:
                        return Decimal('0')

                def parse_extra_costs(raw_json):
                    try:
                        rows = json.loads(raw_json or '[]')
                    except Exception:
                        rows = []

                    parsed_rows = []
                    total = Decimal('0.00')
                    if not isinstance(rows, list):
                        return parsed_rows, total

                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        description = str(row.get('description', '')).strip()
                        amount = parse_money(row.get('amount', '0'))
                        if not description and amount <= 0:
                            continue
                        if amount < 0:
                            amount = Decimal('0.00')
                        amount = amount.quantize(Decimal('0.01'))
                        parsed_rows.append({
                            'description': description,
                            'amount': str(amount),
                        })
                        total += amount

                    return parsed_rows, total.quantize(Decimal('0.01'))

                # Parse insurance and tracker inputs early so totals affect the purchase price,
                # balance, and installment plan calculations.
                insurance_provider_id = request.POST.get('insurance_provider_id')
                insurance_policy_number = request.POST.get('insurance_policy_number', '').strip()
                insurance_policy_type = request.POST.get('insurance_policy_type', 'comprehensive')
                insurance_vehicle_usage = request.POST.get('insurance_vehicle_usage', 'private').strip() or 'private'
                insurance_start_date = request.POST.get('insurance_start_date', '').strip()
                insurance_end_date = request.POST.get('insurance_end_date', '').strip()
                insurance_buying_price = request.POST.get('insurance_buying_price', '').strip()
                insurance_selling_price = request.POST.get('insurance_selling_price', '').strip()
                insurance_agent_name = request.POST.get('insurance_agent_name', '').strip()
                insurance_agent_id = request.POST.get('insurance_agent_id', '').strip()
                insurance_payment_type = request.POST.get('insurance_payment_type', 'full').strip()
                insurance_has_plan = (insurance_payment_type == 'flexible')
                insurance_flexible_json = request.POST.get('insurance_flexible_installments_json', '[]')
                insurance_interest_rate = request.POST.get('insurance_interest_rate', '0').strip()

                tracker_names = request.POST.getlist('tracker_name[]')
                tracker_serials = request.POST.getlist('tracker_serial[]')
                tracker_certificate_numbers = request.POST.getlist('tracker_certificate_number[]')
                tracker_providers = request.POST.getlist('tracker_provider[]')
                tracker_install_dates = request.POST.getlist('tracker_install_date[]')
                tracker_buying_prices = request.POST.getlist('tracker_buying_price[]')
                tracker_selling_prices = request.POST.getlist('tracker_selling_price[]')
                tracker_payment_types = request.POST.getlist('tracker_payment_type[]')
                tracker_flex_jsons = request.POST.getlist('tracker_flexible_installments_json[]')
                tracker_interest_rates = request.POST.getlist('tracker_interest_rate[]')

                commission_addon = parse_money(client_vehicle.commission_amount)

                insurance_addon = Decimal('0')
                if insurance_provider_id and insurance_policy_number and insurance_start_date and insurance_end_date:
                    insurance_addon = parse_money(insurance_selling_price)

                tracker_addon = Decimal('0')
                for i, name in enumerate(tracker_names):
                    if name.strip():
                        tracker_addon += parse_money(tracker_selling_prices[i] if i < len(tracker_selling_prices) else '0')

                auto_client_purchase_price = (
                    parse_money(client_vehicle.vehicle.selling_price)
                    + insurance_addon
                    + tracker_addon
                    + commission_addon
                ).quantize(Decimal('0.01'))

                extra_cost_rows, extra_costs_total = parse_extra_costs(request.POST.get('extra_costs_json', '[]'))
                final_selling_price = parse_money(request.POST.get('final_selling_price', auto_client_purchase_price))
                if final_selling_price == Decimal('0') and auto_client_purchase_price > 0:
                    final_selling_price = auto_client_purchase_price
                final_selling_price = final_selling_price.quantize(Decimal('0.01'))

                effective_client_price = (final_selling_price - extra_costs_total).quantize(Decimal('0.01'))
                if effective_client_price < 0:
                    effective_client_price = Decimal('0.00')

                client_vehicle.client_purchase_price = auto_client_purchase_price
                client_vehicle.final_selling_price = final_selling_price
                client_vehicle.extra_costs_total = extra_costs_total
                client_vehicle.extra_costs_json = json.dumps(extra_cost_rows)
                client_vehicle.purchase_price = effective_client_price

                if client_vehicle.payment_type == 'full':
                    client_vehicle.deposit_paid = client_vehicle.purchase_price
                
                # Calculate balance
                client_vehicle.balance = (
                    client_vehicle.purchase_price - client_vehicle.deposit_paid
                )
                client_vehicle.total_paid = client_vehicle.deposit_paid
                
                client_vehicle.save()

                # Record deposit payment with optional split methods
                if client_vehicle.deposit_paid > 0:
                    deposit_date = client_vehicle.purchase_date or timezone.now().date()
                    deposit_split_methods = request.POST.getlist('deposit_split_method[]')
                    deposit_split_amounts = request.POST.getlist('deposit_split_amount[]')
                    deposit_split_references = request.POST.getlist('deposit_split_reference[]')

                    # Build valid splits (method + positive amount required)
                    valid_splits = []
                    for m, a, r in zip(deposit_split_methods, deposit_split_amounts, deposit_split_references):
                        if m and a:
                            try:
                                amt = Decimal(str(a).replace(',', ''))
                                if amt > 0:
                                    valid_splits.append((m, amt, r.strip() if r else None))
                            except Exception:
                                pass

                    if len(valid_splits) > 1:
                        deposit_payment = Payment.objects.create(
                            client_vehicle=client_vehicle,
                            amount=client_vehicle.deposit_paid,
                            payment_date=deposit_date,
                            payment_method='mixed',
                            notes='Initial deposit — vehicle assignment',
                            recorded_by=request.user,
                        )
                        for method, amt, ref in valid_splits:
                            PaymentSplit.objects.create(
                                payment=deposit_payment,
                                payment_method=method,
                                amount=amt,
                                transaction_reference=ref,
                            )
                    elif len(valid_splits) == 1:
                        method, amt, ref = valid_splits[0]
                        Payment.objects.create(
                            client_vehicle=client_vehicle,
                            amount=client_vehicle.deposit_paid,
                            payment_date=deposit_date,
                            payment_method=method,
                            transaction_reference=ref,
                            notes='Initial deposit — vehicle assignment',
                            recorded_by=request.user,
                        )
                    else:
                        # No split info — use single method fallback
                        single_method = request.POST.get('deposit_payment_method', 'cash') or 'cash'
                        single_ref = request.POST.get('deposit_transaction_reference', '').strip() or None
                        Payment.objects.create(
                            client_vehicle=client_vehicle,
                            amount=client_vehicle.deposit_paid,
                            payment_date=deposit_date,
                            payment_method=single_method,
                            transaction_reference=single_ref,
                            notes='Initial deposit — vehicle assignment',
                            recorded_by=request.user,
                        )

                # Update vehicle status
                vehicle = client_vehicle.vehicle
                vehicle.status = 'sold'
                vehicle.save()
                
                # Update client status
                client.status = 'active'
                client.save()

                flexible_installments = []
                if client_vehicle.payment_type == 'flexible':
                    try:
                        flexible_installments = json.loads(request.POST.get('flexible_installments_json', '[]'))
                    except json.JSONDecodeError:
                        flexible_installments = []
                
                # Create Installment Plan based on payment type
                # Only create plan if payment_type is 'installment' or 'flexible' (not 'full')
                if client_vehicle.balance > 0 and client_vehicle.payment_type in ['installment', 'flexible']:
                    from apps.payments.models import InstallmentPlan

                    installment_count = client_vehicle.installment_months or 1
                    plan_start_date = timezone.now().date()
                    monthly_amount = client_vehicle.monthly_installment

                    if client_vehicle.payment_type == 'flexible' and flexible_installments:
                        installment_count = len(flexible_installments)
                        first_due_date = str(flexible_installments[0].get('due_date', '')).strip()
                        if first_due_date:
                            plan_start_date = datetime.strptime(first_due_date, '%Y-%m-%d').date()
                        monthly_amount = (client_vehicle.balance / Decimal(str(installment_count))).quantize(Decimal('0.01'))

                    plan = InstallmentPlan.objects.create(
                        client_vehicle=client_vehicle,
                        total_amount=client_vehicle.purchase_price,
                        deposit=client_vehicle.deposit_paid,
                        monthly_installment=monthly_amount,
                        number_of_installments=installment_count,
                        start_date=plan_start_date,
                        is_active=True,
                        created_by=request.user
                    )

                    # For flexible mode, replace auto-generated schedule with custom dates/amounts.
                    if client_vehicle.payment_type == 'flexible' and flexible_installments:
                        from apps.payments.models import PaymentSchedule

                        plan.payment_schedules.all().delete()
                        for idx, installment in enumerate(flexible_installments, start=1):
                            due_date = datetime.strptime(str(installment.get('due_date')).strip(), '%Y-%m-%d').date()
                            amount_due = Decimal(str(installment.get('amount')).strip())
                            PaymentSchedule.objects.create(
                                installment_plan=plan,
                                installment_number=idx,
                                due_date=due_date,
                                amount_due=amount_due
                            )
                
                # --- Handle Insurance ---
                try:
                    _upsert_insurance_policy(
                        request=request,
                        client=client,
                        vehicle=vehicle,
                        client_vehicle=client_vehicle,
                        insurance_data=request.POST,
                    )
                except Exception as e:
                    messages.warning(request, f'Vehicle assigned but insurance could not be saved: {e}')
                
                # --- Handle Multiple Trackers ---
                for i, name in enumerate(tracker_names):
                    if name.strip():
                        try:
                            from apps.clients.models import VehicleTracker
                            from datetime import datetime as dt
                            
                            payment_type = tracker_payment_types[i] if i < len(tracker_payment_types) else 'full'
                            has_plan = (payment_type == 'flexible')
                            install_date = tracker_install_dates[i] if i < len(tracker_install_dates) and tracker_install_dates[i] else timezone.now().date()

                            # Parse flexible installments from JSON
                            import json as _json
                            tracker_months = None
                            tracker_monthly = None
                            if has_plan:
                                flex_json = tracker_flex_jsons[i] if i < len(tracker_flex_jsons) else '[]'
                                try:
                                    trk_installments = _json.loads(flex_json or '[]')
                                except Exception:
                                    trk_installments = []
                                if trk_installments:
                                    tracker_months = len(trk_installments)
                                    total_trk = sum(
                                        Decimal(str(row.get('amount', '0') or '0'))
                                        for row in trk_installments
                                    )
                                    tracker_monthly = total_trk / tracker_months if tracker_months else None
                            
                            VehicleTracker.objects.create(
                                client_vehicle=client_vehicle,
                                tracker_name=name,
                                serial_number=tracker_serials[i] if i < len(tracker_serials) else '',
                                certificate_number=tracker_certificate_numbers[i] if i < len(tracker_certificate_numbers) else '',
                                provider=tracker_providers[i] if i < len(tracker_providers) else '',
                                buying_price=Decimal(tracker_buying_prices[i]) if i < len(tracker_buying_prices) and tracker_buying_prices[i] else Decimal('0'),
                                selling_price=Decimal(tracker_selling_prices[i]) if i < len(tracker_selling_prices) and tracker_selling_prices[i] else Decimal('0'),
                                payment_type=payment_type,
                                has_payment_plan=has_plan,
                                deposit=(Decimal(tracker_selling_prices[i]) if payment_type == 'deduct_from_deposit' and i < len(tracker_selling_prices) and tracker_selling_prices[i] else Decimal('0')),
                                installment_months=tracker_months if has_plan else None,
                                monthly_installment=tracker_monthly if has_plan else None,
                                interest_rate=Decimal('0'),
                                total_paid=(Decimal(tracker_selling_prices[i]) if payment_type == 'deduct_from_deposit' and i < len(tracker_selling_prices) and tracker_selling_prices[i] else Decimal('0')),
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
        # Check if vehicle_id is provided via query parameter (from quick-sell feature)
        vehicle_id = request.GET.get('vehicle_id')
        initial_data = {}
        
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(pk=vehicle_id, status='available')
                initial_data['vehicle'] = vehicle
            except Vehicle.DoesNotExist:
                messages.warning(request, 'Selected vehicle is not available.')
        
        form = ClientVehicleForm(client=client, initial=initial_data)
    
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
    from apps.insurance.models import InsurancePolicy
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta
    
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
    currently_due_schedule = Decimal('0.00')
    
    monthly_installment_display = client_vehicle.monthly_installment or Decimal('0.00')
    next_installment_date_display = None
    interest_rate_display = Decimal('0.00')
    today = timezone.now().date()

    if installment_plan:
        # Get next unpaid installment
        next_payment = PaymentSchedule.objects.filter(
            installment_plan=installment_plan,
            is_paid=False
        ).order_by('due_date').first()
        next_installment_date_display = next_payment.due_date if next_payment else None
        
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
        
        # Calculate currently due (past and present due dates only, excluding future dates)
        currently_due_schedule = all_schedules.filter(
            is_paid=False,
            due_date__lte=today
        ).aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')

        unpaid_count = all_schedules.filter(is_paid=False).count()
        if unpaid_count > 0 and total_remaining_schedule > 0:
            monthly_installment_display = (total_remaining_schedule / Decimal(str(unpaid_count))).quantize(Decimal('0.01'))
        elif installment_plan.monthly_installment:
            monthly_installment_display = installment_plan.monthly_installment
    elif client_vehicle.payment_type == 'installment' and client_vehicle.installment_months and client_vehicle.balance > 0:
        monthly_installment_display = (client_vehicle.balance / Decimal(str(client_vehicle.installment_months))).quantize(Decimal('0.01'))

        if client_vehicle.monthly_payment_date:
            candidate = today.replace(day=1)
            day = min(max(client_vehicle.monthly_payment_date, 1), 28)
            candidate = candidate.replace(day=day)
            if candidate <= today:
                candidate = (candidate + relativedelta(months=1)).replace(day=day)
            next_installment_date_display = candidate

    today = timezone.now().date()

    # Insurance payment summary (latest policy for this client vehicle)
    insurance_policy = InsurancePolicy.objects.filter(
        vehicle=client_vehicle.vehicle,
        client=client_vehicle.client,
    ).order_by('-created_at').first()

    insurance_summary = None
    if insurance_policy:
        insurance_schedules = insurance_policy.insurance_payment_schedules.all()
        insurance_total_paid = insurance_schedules.aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0.00')

        if insurance_policy.has_payment_plan and insurance_schedules.exists():
            insurance_total_due = insurance_schedules.aggregate(total=models.Sum('amount_due'))['total'] or Decimal('0.00')
            insurance_balance = max(Decimal('0.00'), insurance_total_due - insurance_total_paid)
            insurance_next_payment = insurance_schedules.filter(is_paid=False).order_by('due_date').first()
            insurance_monthly = insurance_policy.insurance_monthly_installment or (
                insurance_next_payment.amount_due if insurance_next_payment else Decimal('0.00')
            )
            insurance_is_defaulted = insurance_schedules.filter(is_paid=False, due_date__lt=today).exists()
        else:
            insurance_balance = max(Decimal('0.00'), (insurance_policy.selling_price or Decimal('0.00')) - insurance_total_paid)
            insurance_next_payment = None
            insurance_monthly = Decimal('0.00')
            insurance_is_defaulted = False

        insurance_summary = {
            'policy': insurance_policy,
            'monthly_installment': insurance_monthly,
            'next_payment': insurance_next_payment,
            'total_paid': insurance_total_paid,
            'balance': insurance_balance,
            'is_defaulted': insurance_is_defaulted,
            'is_fully_paid': insurance_balance <= Decimal('0.00'),
        }

    # Tracker payment summary
    tracker_payment_rows = []
    for tracker in client_vehicle.trackers.all():
        next_due_date = None
        is_defaulted = False

        if tracker.has_payment_plan and tracker.monthly_installment and tracker.monthly_installment > 0 and tracker.installment_months:
            paid_installments = int((tracker.total_paid or Decimal('0.00')) / tracker.monthly_installment)
            next_installment_number = paid_installments + 1

            if tracker.balance > 0 and next_installment_number <= tracker.installment_months and tracker.installed_date:
                next_due_date = tracker.installed_date + relativedelta(months=next_installment_number)
                is_defaulted = next_due_date < today

        tracker_payment_rows.append({
            'tracker': tracker,
            'monthly_installment': tracker.monthly_installment if tracker.has_payment_plan else Decimal('0.00'),
            'next_due_date': next_due_date,
            'total_paid': tracker.total_paid,
            'balance': tracker.balance,
            'is_defaulted': is_defaulted,
            'is_fully_paid': tracker.balance <= Decimal('0.00'),
        })
    
    context = {
        'client_vehicle': client_vehicle,
        'payments': payments,
        'installment_plan': installment_plan,
        'payment_progress': client_vehicle.payment_progress,
        'next_payment': next_payment,
        'total_paid_schedule': total_paid_schedule,
        'total_remaining_schedule': total_remaining_schedule,
        'currently_due_schedule': currently_due_schedule,
        'monthly_installment_display': monthly_installment_display,
        'next_installment_date_display': next_installment_date_display,
        'interest_rate_display': interest_rate_display,
        'insurance_summary': insurance_summary,
        'tracker_payment_rows': tracker_payment_rows,
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
            updated_client_vehicle = form.save(commit=False)
            updated_client_vehicle.client = client_vehicle.client

            def parse_money(value):
                try:
                    return Decimal(str(value).strip() or '0')
                except Exception:
                    return Decimal('0')

            def parse_extra_costs(raw_json):
                try:
                    rows = json.loads(raw_json or '[]')
                except Exception:
                    rows = []

                parsed_rows = []
                total = Decimal('0.00')
                if not isinstance(rows, list):
                    return parsed_rows, total

                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    description = str(row.get('description', '')).strip()
                    amount = parse_money(row.get('amount', '0'))
                    if not description and amount <= 0:
                        continue
                    if amount < 0:
                        amount = Decimal('0.00')
                    amount = amount.quantize(Decimal('0.01'))
                    parsed_rows.append({
                        'description': description,
                        'amount': str(amount),
                    })
                    total += amount

                return parsed_rows, total.quantize(Decimal('0.01'))

            insurance_provider_id = request.POST.get('insurance_provider_id')
            insurance_policy_number = request.POST.get('insurance_policy_number', '').strip()
            insurance_start_date = request.POST.get('insurance_start_date', '').strip()
            insurance_end_date = request.POST.get('insurance_end_date', '').strip()
            insurance_selling_price = request.POST.get('insurance_selling_price', '').strip()
            tracker_names = request.POST.getlist('tracker_name[]')
            tracker_selling_prices = request.POST.getlist('tracker_selling_price[]')

            commission_addon = parse_money(updated_client_vehicle.commission_amount)
            insurance_addon = Decimal('0.00')
            if insurance_provider_id and insurance_policy_number and insurance_start_date and insurance_end_date:
                insurance_addon = parse_money(insurance_selling_price)

            tracker_addon = Decimal('0.00')
            for i, name in enumerate(tracker_names):
                if name.strip():
                    tracker_addon += parse_money(tracker_selling_prices[i] if i < len(tracker_selling_prices) else '0')

            auto_client_purchase_price = (
                parse_money(updated_client_vehicle.vehicle.selling_price)
                + insurance_addon
                + tracker_addon
                + commission_addon
            ).quantize(Decimal('0.01'))

            extra_cost_rows, extra_costs_total = parse_extra_costs(request.POST.get('extra_costs_json', '[]'))
            final_selling_price = parse_money(request.POST.get('final_selling_price', auto_client_purchase_price))
            if final_selling_price == Decimal('0') and auto_client_purchase_price > 0:
                final_selling_price = auto_client_purchase_price
            final_selling_price = final_selling_price.quantize(Decimal('0.01'))

            effective_client_price = (final_selling_price - extra_costs_total).quantize(Decimal('0.01'))
            if effective_client_price < 0:
                effective_client_price = Decimal('0.00')

            updated_client_vehicle.client_purchase_price = auto_client_purchase_price
            updated_client_vehicle.final_selling_price = final_selling_price
            updated_client_vehicle.extra_costs_total = extra_costs_total
            updated_client_vehicle.extra_costs_json = json.dumps(extra_cost_rows)
            updated_client_vehicle.purchase_price = effective_client_price

            if updated_client_vehicle.payment_type == 'full':
                updated_client_vehicle.deposit_paid = updated_client_vehicle.purchase_price

            updated_client_vehicle.balance = updated_client_vehicle.purchase_price - (updated_client_vehicle.total_paid or Decimal('0.00'))
            if updated_client_vehicle.balance < Decimal('0.00'):
                updated_client_vehicle.balance = Decimal('0.00')

            updated_client_vehicle.save()
            client_vehicle = updated_client_vehicle

            existing_policy = None
            try:
                from apps.insurance.models import InsurancePolicy
                existing_policy = InsurancePolicy.objects.filter(
                    vehicle=client_vehicle.vehicle,
                    client=client_vehicle.client,
                ).order_by('-created_at').first()
            except Exception:
                existing_policy = None

            try:
                _upsert_insurance_policy(
                    request=request,
                    client=client_vehicle.client,
                    vehicle=client_vehicle.vehicle,
                    client_vehicle=client_vehicle,
                    insurance_data=request.POST,
                    existing_policy=existing_policy,
                )
            except Exception as e:
                messages.warning(request, f'Assignment updated but insurance could not be saved: {e}')
            
            # Automatically create Installment Plan if there's a balance and payment terms are provided
            if client_vehicle.balance > 0 and client_vehicle.installment_months:
                from apps.payments.models import InstallmentPlan
                # ClientVehicle no longer stores interest_rate; default to zero when creating/updating plans.
                default_interest_rate = Decimal('0.00')
                plan, created = InstallmentPlan.objects.get_or_create(
                    client_vehicle=client_vehicle,
                    defaults={
                        'total_amount': client_vehicle.purchase_price,
                        'deposit': client_vehicle.deposit_paid,
                        'monthly_installment': client_vehicle.monthly_installment,
                        'number_of_installments': client_vehicle.installment_months,
                        'interest_rate': default_interest_rate,
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
                    plan.interest_rate = default_interest_rate
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

    # Prefill insurance and tracker sections for edit mode.
    from apps.insurance.models import InsuranceProvider, InsurancePolicy

    insurance_providers = InsuranceProvider.objects.filter(is_active=True).order_by('name')
    insurance_policy = InsurancePolicy.objects.filter(
        vehicle=client_vehicle.vehicle,
        client=client_vehicle.client,
    ).order_by('-created_at').first()

    initial_insurance_data = {}
    if insurance_policy:
        insurance_installments = list(
            insurance_policy.insurance_payment_schedules.order_by('installment_number').values('due_date', 'amount_due')
        )
        initial_insurance_data = {
            'provider_id': insurance_policy.provider_id,
            'policy_number': insurance_policy.policy_number,
            'policy_type': insurance_policy.policy_type,
            'vehicle_usage': insurance_policy.vehicle_usage or 'private',
            'start_date': insurance_policy.start_date.isoformat() if insurance_policy.start_date else '',
            'end_date': insurance_policy.end_date.isoformat() if insurance_policy.end_date else '',
            'buying_price': str(insurance_policy.buying_price or Decimal('0.00')),
            'selling_price': str(insurance_policy.selling_price or Decimal('0.00')),
            'agent_name': insurance_policy.agent_name or '',
            'agent_id': insurance_policy.agent_id or '',
            'payment_type': insurance_policy.payment_type or 'full',
            'flexible_installments': [
                {
                    'due_date': row['due_date'].isoformat() if row['due_date'] else '',
                    'amount': str(row['amount_due'] or Decimal('0.00')),
                }
                for row in insurance_installments
            ],
        }

    initial_trackers_data = []
    for tracker in client_vehicle.trackers.all().order_by('created_at'):
        installments = []
        if tracker.has_payment_plan and tracker.installment_months and tracker.monthly_installment:
            base_date = tracker.installed_date or timezone.now().date()
            for idx in range(int(tracker.installment_months)):
                installments.append({
                    'due_date': (base_date + relativedelta(months=idx + 1)).isoformat(),
                    'amount': str(tracker.monthly_installment),
                })

        initial_trackers_data.append({
            'tracker_name': tracker.tracker_name or '',
            'serial_number': tracker.serial_number or '',
            'certificate_number': tracker.certificate_number or '',
            'provider': tracker.provider or '',
            'install_date': tracker.installed_date.isoformat() if tracker.installed_date else '',
            'buying_price': str(tracker.buying_price or Decimal('0.00')),
            'selling_price': str(tracker.selling_price or Decimal('0.00')),
            'payment_type': tracker.payment_type or 'full',
            'flexible_installments': installments,
        })
    
    context = {
        'form': form,
        'client': client_vehicle.client,
        'client_vehicle': client_vehicle,
        'title': 'Update Vehicle Assignment',
        'button_text': 'Update Assignment',
        'vehicle_prices_json': json.dumps(vehicle_prices),
        'vehicle_cost_prices_json': json.dumps(vehicle_cost_prices),
        'insurance_providers': insurance_providers,
        'initial_insurance_json': json.dumps(initial_insurance_data),
        'initial_trackers_json': json.dumps(initial_trackers_data),
    }
    
    return render(request, 'clients/assign_vehicle.html', context)


@login_required
def download_sales_agreement(request, client_vehicle_pk):
    """
    Download sales agreement PDF for a vehicle purchase
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=client_vehicle_pk)
    
    # Only client portal users are restricted to their own vehicles.
    client_profile = getattr(request.user, 'client_profile', None)
    if request.user.role == UserRole.CLIENT and client_profile != client_vehicle.client:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from apps.documents.sales_agreement_pdf import generate_sales_agreement_pdf
        
        pdf_buffer = generate_sales_agreement_pdf(client_vehicle)
        
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        filename = f"Sales_Agreement_{client_vehicle.vehicle.registration_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        log_audit(
            request.user, 'download', 'ClientVehicle',
            f'Downloaded sales agreement for {client_vehicle.client.get_full_name()}'
        )
        
        return response
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('clients:client_vehicle_detail', pk=client_vehicle_pk)


# ==================== PAYMENT VIEWS ====================

@login_required
def record_payment(request, client_vehicle_pk):
    """
    Record a payment for a client's vehicle (supports split payment methods)
    """
    client_vehicle = get_object_or_404(ClientVehicle, pk=client_vehicle_pk)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, client_vehicle=client_vehicle)
        if form.is_valid():
            with transaction.atomic():
                # Collect split method data
                split_methods = request.POST.getlist('split_method[]')
                split_amounts = request.POST.getlist('split_amount[]')
                split_references = request.POST.getlist('split_reference[]')

                valid_splits = []
                for m, a, r in zip(split_methods, split_amounts, split_references):
                    if m and a:
                        try:
                            amt = Decimal(str(a).replace(',', ''))
                            if amt > 0:
                                valid_splits.append((m, amt, r.strip() if r else None))
                        except Exception:
                            pass

                payment = form.save(commit=False)
                payment.client_vehicle = client_vehicle
                payment.recorded_by = request.user

                if len(valid_splits) > 1:
                    payment.payment_method = 'mixed'
                elif len(valid_splits) == 1:
                    payment.payment_method = valid_splits[0][0]

                payment.save()

                # Create PaymentSplit records for multi-method payments
                if len(valid_splits) > 1:
                    for method, amt, ref in valid_splits:
                        PaymentSplit.objects.create(
                            payment=payment,
                            payment_method=method,
                            amount=amt,
                            transaction_reference=ref,
                        )

                # Update payment schedules if an installment plan exists
                try:
                    from apps.payments.views import update_payment_schedules
                    update_payment_schedules(payment, client_vehicle)
                except Exception:
                    pass

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
            'interest_rate': Decimal('0.00'),
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
    Redirect to the canonical defaulters report in payments.
    """
    log_audit(request.user, 'view', 'Client', 'Redirected defaulters report to payments module')
    return redirect('payments:defaulters_report')


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