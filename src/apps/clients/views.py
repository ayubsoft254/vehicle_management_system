"""
Views for the client app
Handles client management, vehicle assignments, payments, and documents
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
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
    
    # Get client's vehicles
    client_vehicles = ClientVehicle.objects.filter(client=client).select_related('vehicle')
    
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
    Assign a vehicle to a client
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    if request.method == 'POST':
        form = ClientVehicleForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                client_vehicle = form.save(commit=False)
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
                
                log_audit(
                    request.user, 'create', 'ClientVehicle',
                    f'Assigned vehicle {vehicle} to client {client.get_full_name()}'
                )
                
                messages.success(
                    request, 
                    f'Vehicle {vehicle} assigned to {client.get_full_name()} successfully!'
                )
                return redirect('clients:client_detail', pk=client.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientVehicleForm(initial={'client': client})
    
    context = {
        'form': form,
        'client': client,
        'title': f'Assign Vehicle to {client.get_full_name()}',
        'button_text': 'Assign Vehicle'
    }
    
    return render(request, 'clients/assign_vehicle.html', context)


@login_required
def client_vehicle_detail(request, pk):
    """
    Display details of a client's vehicle purchase
    """
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
    
    context = {
        'client_vehicle': client_vehicle,
        'payments': payments,
        'installment_plan': installment_plan,
        'payment_progress': client_vehicle.payment_progress,
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
            form.save()
            
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
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'title': 'Update Vehicle Assignment',
        'button_text': 'Update Assignment'
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
        form = PaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.recorded_by = request.user
                payment.save()
                
                # Update client vehicle balance
                client_vehicle.total_paid += payment.amount
                client_vehicle.update_balance()
                
                # Check if fully paid
                if client_vehicle.paid_off:
                    client_vehicle.client.status = 'completed'
                    client_vehicle.client.save()
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
        form = ClientDocumentForm(initial={'client': client})
    
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
        form = InstallmentPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
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
            'client_vehicle': client_vehicle,
            'total_amount': client_vehicle.purchase_price,
            'deposit': client_vehicle.deposit_paid,
            'monthly_installment': client_vehicle.monthly_installment,
            'number_of_installments': client_vehicle.installment_months,
            'interest_rate': client_vehicle.interest_rate,
            'start_date': client_vehicle.purchase_date,
        }
        form = InstallmentPlanForm(initial=initial_data)
    
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