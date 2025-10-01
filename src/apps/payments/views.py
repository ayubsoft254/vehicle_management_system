"""
Views for the payments app
Handles payment recording, installment plans, schedules, and reporting
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json

from .models import Payment, InstallmentPlan, PaymentSchedule, PaymentReminder
from apps.clients.models import Client, ClientVehicle
from apps.audit.utils import log_audit


# ==================== PAYMENT MANAGEMENT VIEWS ====================

@login_required
def payment_list(request):
    """
    Display list of all payments with filtering
    """
    payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'recorded_by'
    ).order_by('-payment_date')
    
    # Filtering
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    payment_method = request.GET.get('payment_method')
    search = request.GET.get('search')
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    
    if search:
        payments = payments.filter(
            Q(receipt_number__icontains=search) |
            Q(transaction_reference__icontains=search) |
            Q(client_vehicle__client__first_name__icontains=search) |
            Q(client_vehicle__client__last_name__icontains=search) |
            Q(client_vehicle__vehicle__registration_number__icontains=search)
        )
    
    # Statistics
    total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    payment_count = payments.count()
    
    # This month statistics
    now = timezone.now()
    this_month_payments = Payment.objects.filter(
        payment_date__year=now.year,
        payment_date__month=now.month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Pagination
    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'payments': page_obj,
        'total_payments': total_payments,
        'payment_count': payment_count,
        'this_month_payments': this_month_payments,
        'payment_methods': Payment.PAYMENT_METHOD_CHOICES,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed payment list')
    
    return render(request, 'payments/payment_list.html', context)


@login_required
def payment_detail(request, pk):
    """
    Display detailed information about a specific payment
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
        'payment': payment,
        'client': payment.client_vehicle.client,
        'vehicle': payment.client_vehicle.vehicle,
        'client_vehicle': payment.client_vehicle,
    }
    
    log_audit(request.user, 'view', 'Payment', f'Viewed payment {payment.receipt_number}')
    
    return render(request, 'payments/payment_detail.html', context)


@login_required
def record_payment(request, client_vehicle_pk):
    """
    Record a new payment for a client vehicle
    """
    from .forms import PaymentForm
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.client_vehicle = client_vehicle
                payment.recorded_by = request.user
                payment.save()
                
                # Update client vehicle balance
                client_vehicle.total_paid += payment.amount
                client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
                
                # Check if fully paid
                if client_vehicle.balance <= 0:
                    client_vehicle.paid_off = True
                    client_vehicle.client.status = 'completed'
                    client_vehicle.client.save()
                    
                    messages.success(
                        request,
                        f'Payment recorded! Vehicle fully paid off! 🎉'
                    )
                else:
                    messages.success(
                        request,
                        f'Payment of KES {payment.amount:,.2f} recorded successfully! '
                        f'Remaining balance: KES {client_vehicle.balance:,.2f}'
                    )
                
                client_vehicle.save()
                
                # Update payment schedule if exists
                update_payment_schedules(payment, client_vehicle)
                
                log_audit(
                    request.user, 'create', 'Payment',
                    f'Recorded payment {payment.receipt_number} for {client_vehicle.client.get_full_name()}'
                )
                
                return redirect('payments:payment_detail', pk=payment.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(initial={'client_vehicle': client_vehicle})
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
    }
    
    return render(request, 'payments/payment_form.html', context)


@login_required
def payment_receipt(request, pk):
    """
    Generate and display payment receipt
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
        'payment': payment,
        'client': payment.client_vehicle.client,
        'vehicle': payment.client_vehicle.vehicle,
        'client_vehicle': payment.client_vehicle,
        'printed_date': timezone.now(),
    }
    
    log_audit(request.user, 'view', 'Payment', f'Generated receipt for {payment.receipt_number}')
    
    return render(request, 'payments/payment_receipt.html', context)


# ==================== INSTALLMENT PLAN VIEWS ====================

@login_required
def installment_plan_list(request):
    """
    Display list of all installment plans
    """
    plans = InstallmentPlan.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'created_by'
    ).order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    
    if status_filter == 'active':
        plans = plans.filter(is_active=True, is_completed=False)
    elif status_filter == 'completed':
        plans = plans.filter(is_completed=True)
    elif status_filter == 'overdue':
        today = timezone.now().date()
        plans = plans.filter(is_active=True, is_completed=False, end_date__lt=today)
    
    if search:
        plans = plans.filter(
            Q(client_vehicle__client__first_name__icontains=search) |
            Q(client_vehicle__client__last_name__icontains=search) |
            Q(client_vehicle__vehicle__registration_number__icontains=search)
        )
    
    # Statistics
    total_plans = plans.count()
    active_plans = plans.filter(is_active=True, is_completed=False).count()
    completed_plans = plans.filter(is_completed=True).count()
    overdue_plans = plans.filter(
        is_active=True,
        is_completed=False,
        end_date__lt=timezone.now().date()
    ).count()
    
    # Pagination
    paginator = Paginator(plans, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'plans': page_obj,
        'total_plans': total_plans,
        'active_plans': active_plans,
        'completed_plans': completed_plans,
        'overdue_plans': overdue_plans,
    }
    
    log_audit(request.user, 'view', 'InstallmentPlan', 'Viewed installment plan list')
    
    return render(request, 'payments/installment_plan_list.html', context)


@login_required
def installment_plan_detail(request, pk):
    """
    Display detailed information about an installment plan
    """
    plan = get_object_or_404(
        InstallmentPlan.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle',
            'created_by'
        ),
        pk=pk
    )
    
    # Get payment schedules
    schedules = plan.payment_schedules.all().order_by('installment_number')
    
    # Get all payments for this client vehicle
    payments = Payment.objects.filter(
        client_vehicle=plan.client_vehicle
    ).order_by('-payment_date')
    
    context = {
        'plan': plan,
        'schedules': schedules,
        'payments': payments,
        'client': plan.client_vehicle.client,
        'vehicle': plan.client_vehicle.vehicle,
    }
    
    log_audit(request.user, 'view', 'InstallmentPlan', f'Viewed installment plan {plan.pk}')
    
    return render(request, 'payments/installment_plan_detail.html', context)


@login_required
def create_installment_plan(request, client_vehicle_pk):
    """
    Create a new installment plan
    """
    from .forms import InstallmentPlanForm
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    # Check if plan already exists
    if hasattr(client_vehicle, 'installment_plan'):
        messages.warning(request, 'An installment plan already exists for this vehicle.')
        return redirect('payments:installment_plan_detail', pk=client_vehicle.installment_plan.pk)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.client_vehicle = client_vehicle
                plan.created_by = request.user
                plan.save()
                
                # Generate payment schedules
                plan.generate_payment_schedule()
                
                log_audit(
                    request.user, 'create', 'InstallmentPlan',
                    f'Created installment plan for {client_vehicle.client.get_full_name()}'
                )
                
                messages.success(request, 'Installment plan created successfully!')
                return redirect('payments:installment_plan_detail', pk=plan.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill form with client vehicle data
        initial_data = {
            'total_amount': client_vehicle.purchase_price,
            'deposit': client_vehicle.deposit_paid,
            'monthly_installment': client_vehicle.monthly_installment,
            'number_of_installments': client_vehicle.installment_months,
            'interest_rate': client_vehicle.interest_rate or 0,
            'start_date': client_vehicle.purchase_date,
        }
        form = InstallmentPlanForm(initial=initial_data)
    
    context = {
        'form': form,
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
    }
    
    return render(request, 'payments/installment_plan_form.html', context)


@login_required
def update_installment_plan(request, pk):
    """
    Update an existing installment plan
    """
    from .forms import InstallmentPlanForm
    
    plan = get_object_or_404(InstallmentPlan, pk=pk)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            
            log_audit(
                request.user, 'update', 'InstallmentPlan',
                f'Updated installment plan {plan.pk}'
            )
            
            messages.success(request, 'Installment plan updated successfully!')
            return redirect('payments:installment_plan_detail', pk=plan.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InstallmentPlanForm(instance=plan)
    
    context = {
        'form': form,
        'plan': plan,
        'client_vehicle': plan.client_vehicle,
    }
    
    return render(request, 'payments/installment_plan_form.html', context)


@login_required
def regenerate_payment_schedule(request, pk):
    """
    Regenerate payment schedule for an installment plan
    """
    plan = get_object_or_404(InstallmentPlan, pk=pk)
    
    if request.method == 'POST':
        plan.generate_payment_schedule()
        
        log_audit(
            request.user, 'update', 'InstallmentPlan',
            f'Regenerated payment schedule for plan {plan.pk}'
        )
        
        messages.success(request, 'Payment schedule regenerated successfully!')
        return redirect('payments:installment_plan_detail', pk=plan.pk)
    
    context = {
        'plan': plan
    }
    
    return render(request, 'payments/confirm_regenerate_schedule.html', context)


# ==================== PAYMENT SCHEDULE VIEWS ====================

@login_required
def payment_schedule_list(request):
    """
    Display list of payment schedules
    """
    schedules = PaymentSchedule.objects.select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle',
        'payment'
    ).order_by('due_date')
    
    # Filtering
    status_filter = request.GET.get('status')
    
    if status_filter == 'pending':
        schedules = schedules.filter(is_paid=False)
    elif status_filter == 'paid':
        schedules = schedules.filter(is_paid=True)
    elif status_filter == 'overdue':
        schedules = schedules.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        )
    elif status_filter == 'due_this_month':
        now = timezone.now()
        schedules = schedules.filter(
            is_paid=False,
            due_date__year=now.year,
            due_date__month=now.month
        )
    
    # Statistics
    total_schedules = schedules.count()
    pending_schedules = PaymentSchedule.objects.filter(is_paid=False).count()
    paid_schedules = PaymentSchedule.objects.filter(is_paid=True).count()
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    # Pagination
    paginator = Paginator(schedules, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'schedules': page_obj,
        'total_schedules': total_schedules,
        'pending_schedules': pending_schedules,
        'paid_schedules': paid_schedules,
        'overdue_schedules': overdue_schedules,
    }
    
    log_audit(request.user, 'view', 'PaymentSchedule', 'Viewed payment schedule list')
    
    return render(request, 'payments/payment_schedule_list.html', context)


@login_required
def overdue_payments(request):
    """
    Display overdue payment schedules
    """
    today = timezone.now().date()
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    ).order_by('due_date')
    
    # Calculate totals
    total_overdue_amount = overdue_schedules.aggregate(
        Sum('amount_due')
    )['amount_due__sum'] or 0
    
    context = {
        'overdue_schedules': overdue_schedules,
        'total_overdue_amount': total_overdue_amount,
        'total_count': overdue_schedules.count(),
    }
    
    log_audit(request.user, 'view', 'PaymentSchedule', 'Viewed overdue payments')
    
    return render(request, 'payments/overdue_payments.html', context)


# ==================== REPORTING VIEWS ====================

@login_required
def payment_tracker(request, client_vehicle_pk):
    """
    Display payment tracker for a specific client vehicle
    """
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    # Get all payments
    payments = Payment.objects.filter(
        client_vehicle=client_vehicle
    ).order_by('payment_date')
    
    # Get installment plan if exists
    try:
        plan = client_vehicle.installment_plan
        schedules = plan.payment_schedules.all().order_by('installment_number')
    except InstallmentPlan.DoesNotExist:
        plan = None
        schedules = None
    
    context = {
        'client_vehicle': client_vehicle,
        'client': client_vehicle.client,
        'vehicle': client_vehicle.vehicle,
        'payments': payments,
        'plan': plan,
        'schedules': schedules,
    }
    
    log_audit(
        request.user, 'view', 'Payment',
        f'Viewed payment tracker for {client_vehicle.client.get_full_name()}'
    )
    
    return render(request, 'payments/payment_tracker.html', context)


@login_required
def payment_analytics(request):
    """
    Display payment analytics and statistics
    """
    now = timezone.now()
    
    # This month statistics
    this_month_payments = Payment.objects.filter(
        payment_date__year=now.year,
        payment_date__month=now.month
    )
    this_month_total = this_month_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    this_month_count = this_month_payments.count()
    
    # This year statistics
    this_year_payments = Payment.objects.filter(payment_date__year=now.year)
    this_year_total = this_year_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    this_year_count = this_year_payments.count()
    
    # Payment method breakdown
    payment_methods = Payment.objects.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Recent payments
    recent_payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle'
    ).order_by('-payment_date')[:10]
    
    # Overdue statistics
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=now.date()
    )
    overdue_count = overdue_schedules.count()
    overdue_amount = overdue_schedules.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    
    context = {
        'this_month_total': this_month_total,
        'this_month_count': this_month_count,
        'this_year_total': this_year_total,
        'this_year_count': this_year_count,
        'payment_methods': payment_methods,
        'recent_payments': recent_payments,
        'overdue_count': overdue_count,
        'overdue_amount': overdue_amount,
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed payment analytics')
    
    return render(request, 'payments/payment_analytics.html', context)


@login_required
def defaulters_report(request):
    """
    Generate report of clients with overdue payments
    """
    today = timezone.now().date()
    
    # Get all overdue payment schedules
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    ).order_by('due_date')
    
    # Group by client
    defaulters = {}
    for schedule in overdue_schedules:
        client = schedule.installment_plan.client_vehicle.client
        if client not in defaulters:
            defaulters[client] = {
                'client': client,
                'overdue_schedules': [],
                'total_overdue': 0,
                'oldest_due_date': schedule.due_date,
            }
        defaulters[client]['overdue_schedules'].append(schedule)
        defaulters[client]['total_overdue'] += schedule.remaining_amount
    
    context = {
        'defaulters': defaulters.values(),
        'total_defaulters': len(defaulters),
        'total_overdue_amount': sum(d['total_overdue'] for d in defaulters.values()),
    }
    
    log_audit(request.user, 'view', 'Payment', 'Viewed defaulters report')
    
    return render(request, 'payments/defaulters_report.html', context)


@login_required
def export_payments_csv(request):
    """
    Export payments to CSV
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payments_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Receipt Number', 'Client', 'ID Number', 'Vehicle', 
        'Payment Date', 'Amount', 'Payment Method', 
        'Transaction Reference', 'Balance', 'Recorded By'
    ])
    
    payments = Payment.objects.select_related(
        'client_vehicle__client',
        'client_vehicle__vehicle',
        'recorded_by'
    ).order_by('-payment_date')
    
    # Apply filters if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    for payment in payments:
        writer.writerow([
            payment.receipt_number,
            payment.client_vehicle.client.get_full_name(),
            payment.client_vehicle.client.id_number,
            str(payment.client_vehicle.vehicle),
            payment.payment_date.strftime('%Y-%m-%d'),
            payment.amount,
            payment.get_payment_method_display(),
            payment.transaction_reference or '',
            payment.client_vehicle.balance,
            payment.recorded_by.get_full_name() if payment.recorded_by else ''
        ])
    
    log_audit(request.user, 'export', 'Payment', 'Exported payments to CSV')
    
    return response


# ==================== AJAX/API VIEWS ====================

@login_required
def payment_stats_api(request):
    """
    API endpoint for payment statistics
    """
    now = timezone.now()
    
    # Get date range from request
    period = request.GET.get('period', 'month')  # month, year, all
    
    if period == 'month':
        payments = Payment.objects.filter(
            payment_date__year=now.year,
            payment_date__month=now.month
        )
    elif period == 'year':
        payments = Payment.objects.filter(payment_date__year=now.year)
    else:
        payments = Payment.objects.all()
    
    total = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    count = payments.count()
    
    data = {
        'total': float(total),
        'count': count,
        'average': float(total / count) if count > 0 else 0
    }
    
    return JsonResponse(data)


@login_required
def payment_chart_data_api(request):
    """
    API endpoint for payment chart data
    """
    now = timezone.now()
    
    # Get monthly data for the current year
    monthly_data = []
    for month in range(1, 13):
        total = Payment.objects.filter(
            payment_date__year=now.year,
            payment_date__month=month
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        monthly_data.append({
            'month': month,
            'total': float(total)
        })
    
    return JsonResponse({'data': monthly_data})


# ==================== PDF GENERATION VIEWS ====================

@login_required
def generate_agreement_pdf_view(request, client_vehicle_pk):
    """
    Generate and download sales agreement PDF
    """
    from .utils import generate_agreement_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated agreement PDF for {client_vehicle.client.get_full_name()}'
    )
    
    return generate_agreement_pdf(client_vehicle)


@login_required
def generate_proforma_invoice_pdf_view(request, client_vehicle_pk):
    """
    Generate and download proforma invoice PDF
    """
    from .utils import generate_performa_invoice_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated proforma invoice for {client_vehicle.client.get_full_name()}'
    )
    
    return generate_performa_invoice_pdf(client_vehicle)


@login_required
def generate_payment_tracker_pdf_view(request, client_vehicle_pk):
    """
    Generate and download payment tracker PDF
    """
    from .utils import generate_payment_tracker_pdf
    
    client_vehicle = get_object_or_404(
        ClientVehicle.objects.select_related('client', 'vehicle'),
        pk=client_vehicle_pk
    )
    
    log_audit(
        request.user, 'view', 'ClientVehicle',
        f'Generated payment tracker PDF for {client_vehicle.client.get_full_name()}'
    )
    
    return generate_payment_tracker_pdf(client_vehicle)


# ==================== HELPER FUNCTIONS ====================

def update_payment_schedules(payment, client_vehicle):
    """
    Update payment schedules when a payment is made
    """
    try:
        plan = client_vehicle.installment_plan
        pending_schedules = plan.payment_schedules.filter(
            is_paid=False
        ).order_by('installment_number')
        
        remaining_amount = payment.amount
        
        for schedule in pending_schedules:
            if remaining_amount <= 0:
                break
            
            amount_to_apply = min(remaining_amount, schedule.remaining_amount)
            schedule.mark_as_paid(payment, amount_to_apply)
            remaining_amount -= amount_to_apply
        
    except InstallmentPlan.DoesNotExist:
        pass