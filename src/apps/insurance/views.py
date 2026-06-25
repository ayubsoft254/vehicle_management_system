"""
Views for the insurance app
Handles insurance providers, policies, claims, and payments
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
import csv
import json
from decimal import Decimal

from .models import InsuranceAgent, InsurancePolicy, InsuranceClaim, InsurancePayment, InsurancePaymentSchedule
from .forms import (
    InsurancePolicyForm, InsuranceClaimForm,
    ClaimUpdateForm, InsurancePaymentForm, InsurancePolicySearchForm,
    InsuranceClaimSearchForm, PolicyRenewalForm, BulkPolicyReminderForm,
    PolicyCancellationForm, InsuranceQuoteForm, InsuranceAgentForm,
)
from apps.vehicles.models import Vehicle
from apps.clients.models import Client
from apps.audit.utils import log_audit


# ==================== INSURANCE POLICY VIEWS ====================

@login_required
def policy_list(request):
    """
    Display list of all insurance policies with filtering
    """
    policies = InsurancePolicy.objects.select_related(
        'vehicle', 'insurance_agent', 'client', 'created_by'
    ).order_by('-start_date')

    search_form = InsurancePolicySearchForm(request.GET)
    payment_status = request.GET.get('payment_status', '').strip()

    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        policy_type = search_form.cleaned_data.get('policy_type')
        status = search_form.cleaned_data.get('status')
        insurance_agent = search_form.cleaned_data.get('insurance_agent')
        expiring_soon = search_form.cleaned_data.get('expiring_soon')

        if search:
            policies = policies.filter(
                Q(policy_number__icontains=search) |
                Q(vehicle__registration_number__icontains=search) |
                Q(client__first_name__icontains=search) |
                Q(client__last_name__icontains=search)
            )

        if policy_type:
            policies = policies.filter(policy_type=policy_type)

        if status:
            policies = policies.filter(status=status)

        if insurance_agent:
            policies = policies.filter(insurance_agent=insurance_agent)
        
        if expiring_soon:
            policies = policies.filter(
                status='active',
                end_date__lte=timezone.now().date() + timedelta(days=30)
            )

    if payment_status == 'fully_paid':
        policies = policies.filter(insurance_balance__lte=0)
    elif payment_status == 'partial':
        policies = policies.filter(insurance_total_paid__gt=0, insurance_balance__gt=0)
    elif payment_status == 'unpaid':
        policies = policies.filter(insurance_total_paid__lte=0, insurance_balance__gt=0)
    
    # Statistics
    total_policies = policies.count()
    active_policies = policies.filter(status='active').count()
    expiring_policies = policies.filter(
        status='active',
        end_date__lte=timezone.now().date() + timedelta(days=30)
    ).count()
    expired_policies = policies.filter(status='expired').count()

    sold_policies = InsurancePolicy.objects.filter(client__isnull=False)
    total_sold = sold_policies.count()
    fully_paid_count = sold_policies.filter(insurance_balance__lte=0).count()
    partially_paid_count = sold_policies.filter(insurance_total_paid__gt=0, insurance_balance__gt=0).count()
    unpaid_count = sold_policies.filter(insurance_total_paid__lte=0, insurance_balance__gt=0).count()

    sold_totals = sold_policies.aggregate(
        sold_value=Sum('selling_price'),
        paid_value=Sum('insurance_total_paid'),
        balance_value=Sum('insurance_balance')
    )

    insurance_agent_totals = policies.annotate(
        agent_display=Coalesce('agent_name', Value('Unknown'))
    ).values('agent_display').annotate(
        policy_count=Count('pk'),
        total_premium=Coalesce(Sum('selling_price'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_paid=Coalesce(Sum('insurance_total_paid'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_balance=Coalesce(Sum('insurance_balance'), Value(Decimal('0.00'), output_field=DecimalField())),
    ).filter(~Q(agent_display='')).order_by('-total_premium')
    
    # Pagination
    paginator = Paginator(policies, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for policy in page_obj:
        selling_price = policy.selling_price or 0
        total_paid = policy.insurance_total_paid or 0
        balance = policy.insurance_balance or 0

        if selling_price and selling_price > 0:
            policy.payment_progress = min((total_paid / selling_price) * 100, 100)
        else:
            policy.payment_progress = 0

        if balance <= 0:
            policy.payment_status_label = 'Fully Paid'
            policy.payment_status_color = 'green'
        elif total_paid > 0:
            policy.payment_status_label = 'Partially Paid'
            policy.payment_status_color = 'yellow'
        else:
            policy.payment_status_label = 'Unpaid'
            policy.payment_status_color = 'red'
    
    context = {
        'policies': page_obj,
        'search_form': search_form,
        'total_policies': total_policies,
        'active_policies': active_policies,
        'expiring_policies': expiring_policies,
        'expired_policies': expired_policies,
        'payment_status': payment_status,
        'total_sold': total_sold,
        'fully_paid_count': fully_paid_count,
        'partially_paid_count': partially_paid_count,
        'unpaid_count': unpaid_count,
        'total_sold_value': sold_totals.get('sold_value') or 0,
        'total_paid_value': sold_totals.get('paid_value') or 0,
        'total_balance_value': sold_totals.get('balance_value') or 0,
        'insurance_agent_totals': insurance_agent_totals,
    }
    
    log_audit(request.user, 'view', 'InsurancePolicy', 'Viewed policy list')
    
    return render(request, 'insurance/policy_list.html', context)


@login_required
def policy_detail(request, pk):
    """
    Display detailed information about a policy
    """
    policy = get_object_or_404(
        InsurancePolicy.objects.select_related(
            'vehicle', 'insurance_agent', 'client', 'created_by'
        ),
        pk=pk
    )
    
    # Get related data
    claims = InsuranceClaim.objects.filter(policy=policy).order_by('-claim_date')
    payments = InsurancePayment.objects.filter(policy=policy).order_by('-payment_date')
    payment_schedules = policy.insurance_payment_schedules.all().order_by('installment_number')
    
    # Update late fees for all overdue schedules
    for schedule in payment_schedules.filter(is_paid=False):
        schedule.update_late_fees()
    
    context = {
        'policy': policy,
        'claims': claims,
        'payments': payments,
        'payment_schedules': payment_schedules,
        'total_claims': claims.count(),
        'total_payments': payments.aggregate(Sum('amount'))['amount__sum'] or 0,
    }
    
    log_audit(request.user, 'view', 'InsurancePolicy', f'Viewed policy: {policy.policy_number}')
    
    return render(request, 'insurance/policy_detail.html', context)


@login_required
def policy_create(request):
    """
    Create a new insurance policy
    """
    if request.method == 'POST':
        form = InsurancePolicyForm(request.POST, request.FILES)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.created_by = request.user
            policy.save()
            
            log_audit(request.user, 'create', 'InsurancePolicy', f'Created policy: {policy.policy_number}')
            
            messages.success(request, f'Insurance policy "{policy.policy_number}" created successfully!')
            return redirect('insurance:policy_detail', pk=policy.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InsurancePolicyForm()
    
    context = {
        'form': form,
        'title': 'Create Insurance Policy',
        'button_text': 'Create Policy'
    }
    
    return render(request, 'insurance/policy_form.html', context)


@login_required
def policy_update(request, pk):
    """
    Update an existing policy
    """
    policy = get_object_or_404(InsurancePolicy, pk=pk)
    
    if request.method == 'POST':
        form = InsurancePolicyForm(request.POST, request.FILES, instance=policy)
        if form.is_valid():
            form.save()
            
            log_audit(request.user, 'update', 'InsurancePolicy', f'Updated policy: {policy.policy_number}')
            
            messages.success(request, f'Policy "{policy.policy_number}" updated successfully!')
            return redirect('insurance:policy_detail', pk=policy.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InsurancePolicyForm(instance=policy)
    
    context = {
        'form': form,
        'policy': policy,
        'title': f'Update Policy: {policy.policy_number}',
        'button_text': 'Update Policy'
    }
    
    return render(request, 'insurance/policy_form.html', context)


@login_required
def policy_renew(request, pk):
    """
    Renew an existing policy
    """
    old_policy = get_object_or_404(InsurancePolicy, pk=pk)
    
    if request.method == 'POST':
        form = PolicyRenewalForm(request.POST, request.FILES, old_policy=old_policy)
        if form.is_valid():
            with transaction.atomic():
                new_agent = form.cleaned_data.get('insurance_agent') or old_policy.insurance_agent
                # Create new policy
                new_policy = InsurancePolicy.objects.create(
                    vehicle=old_policy.vehicle,
                    client=old_policy.client,
                    insurance_agent=new_agent,
                    agent_name=new_agent.name if new_agent else old_policy.agent_name,
                    agent_id=old_policy.agent_id,
                    policy_number=form.cleaned_data['new_policy_number'],
                    policy_type=form.cleaned_data['policy_type'],
                    vehicle_usage=form.cleaned_data['vehicle_usage'],
                    start_date=form.cleaned_data['new_start_date'],
                    end_date=form.cleaned_data['new_end_date'],
                    premium_amount=form.cleaned_data['new_premium_amount'],
                    sum_insured=form.cleaned_data['new_sum_insured'],
                    excess_amount=form.cleaned_data.get('new_excess_amount') or Decimal('0.00'),
                    buying_price=form.cleaned_data.get('buying_price') or Decimal('0.00'),
                    selling_price=form.cleaned_data.get('selling_price') or Decimal('0.00'),
                    status='active',
                    created_by=request.user
                )

                # Save certificate if uploaded
                cert = form.cleaned_data.get('new_certificate')
                if cert:
                    new_policy.certificate = cert
                    new_policy.save(update_fields=['certificate'])

                # Mark old policy as renewed
                old_policy.status = 'renewed'
                old_policy.save()

                log_audit(
                    request.user, 'create', 'InsurancePolicy',
                    f'Renewed policy {old_policy.policy_number} to {new_policy.policy_number}'
                )
                
                messages.success(
                    request,
                    f'Policy renewed successfully! New policy number: {new_policy.policy_number}'
                )
                return redirect('insurance:policy_detail', pk=new_policy.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PolicyRenewalForm(old_policy=old_policy)
    
    context = {
        'form': form,
        'old_policy': old_policy,
        'title': f'Renew Policy: {old_policy.policy_number}',
        'button_text': 'Renew Policy'
    }
    
    return render(request, 'insurance/policy_renew.html', context)


@login_required
def policy_cancel(request, pk):
    """
    Cancel an insurance policy
    """
    policy = get_object_or_404(InsurancePolicy, pk=pk)
    
    if request.method == 'POST':
        form = PolicyCancellationForm(request.POST)
        if form.is_valid():
            policy.status = 'cancelled'
            policy.notes = f"Cancelled on {form.cleaned_data['cancellation_date']}\n" \
                          f"Reason: {form.cleaned_data.get('cancellation_reason')}\n" \
                          f"Notes: {form.cleaned_data.get('notes', '')}"
            policy.save()
            
            log_audit(
                request.user, 'update', 'InsurancePolicy',
                f'Cancelled policy: {policy.policy_number}'
            )
            
            messages.success(request, f'Policy "{policy.policy_number}" has been cancelled.')
            return redirect('insurance:policy_detail', pk=policy.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PolicyCancellationForm()
    
    context = {
        'form': form,
        'policy': policy
    }
    
    return render(request, 'insurance/policy_cancel.html', context)


@login_required
def expiring_policies(request):
    """
    Display policies expiring soon
    """
    days = int(request.GET.get('days', 30))
    
    expiring = InsurancePolicy.objects.filter(
        status='active',
        end_date__lte=timezone.now().date() + timedelta(days=days),
        end_date__gte=timezone.now().date()
    ).select_related('vehicle', 'client').order_by('end_date')
    
    context = {
        'expiring_policies': expiring,
        'days': days,
        'total_count': expiring.count(),
    }
    
    log_audit(request.user, 'view', 'InsurancePolicy', f'Viewed expiring policies ({days} days)')
    
    return render(request, 'insurance/expiring_policies.html', context)


# ==================== INSURANCE CLAIM VIEWS ====================

@login_required
def claim_list(request):
    """
    Display list of all insurance claims
    """
    claims = InsuranceClaim.objects.select_related(
        'policy__vehicle', 'policy__provider', 'policy__client', 'filed_by'
    ).order_by('-claim_date')
    
    # Apply filters
    search_form = InsuranceClaimSearchForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        claim_type = search_form.cleaned_data.get('claim_type')
        status = search_form.cleaned_data.get('status')
        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')
        
        if search:
            claims = claims.filter(
                Q(claim_number__icontains=search) |
                Q(policy__policy_number__icontains=search) |
                Q(policy__vehicle__registration_number__icontains=search) |
                Q(policy__client__first_name__icontains=search) |
                Q(policy__client__last_name__icontains=search)
            )
        
        if claim_type:
            claims = claims.filter(claim_type=claim_type)
        
        if status:
            claims = claims.filter(status=status)
        
        if date_from:
            claims = claims.filter(claim_date__gte=date_from)
        
        if date_to:
            claims = claims.filter(claim_date__lte=date_to)
    
    # Statistics
    total_claims = claims.count()
    pending_claims = claims.filter(status__in=['pending', 'under_review']).count()
    approved_claims = claims.filter(status='approved').count()
    settled_claims = claims.filter(status='settled').count()
    total_claimed = claims.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    total_approved = claims.aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    
    # Pagination
    paginator = Paginator(claims, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'claims': page_obj,
        'search_form': search_form,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'approved_claims': approved_claims,
        'settled_claims': settled_claims,
        'total_claimed': total_claimed,
        'total_approved': total_approved,
    }
    
    log_audit(request.user, 'view', 'InsuranceClaim', 'Viewed claim list')
    
    return render(request, 'insurance/claim_list.html', context)


@login_required
def claim_detail(request, pk):
    """
    Display detailed information about a claim
    """
    claim = get_object_or_404(
        InsuranceClaim.objects.select_related(
            'policy__vehicle', 'policy__provider', 'policy__client', 'filed_by'
        ),
        pk=pk
    )
    
    context = {
        'claim': claim
    }
    
    log_audit(request.user, 'view', 'InsuranceClaim', f'Viewed claim: {claim.claim_number}')
    
    return render(request, 'insurance/claim_detail.html', context)


@login_required
def claim_create(request):
    """
    File a new insurance claim
    """
    if request.method == 'POST':
        form = InsuranceClaimForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.filed_by = request.user
            claim.save()
            
            log_audit(request.user, 'create', 'InsuranceClaim', f'Filed claim: {claim.claim_number}')
            
            messages.success(request, f'Insurance claim "{claim.claim_number}" filed successfully!')
            return redirect('insurance:claim_detail', pk=claim.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InsuranceClaimForm()
    
    context = {
        'form': form,
        'title': 'File Insurance Claim',
        'button_text': 'File Claim'
    }
    
    return render(request, 'insurance/claim_form.html', context)


@login_required
def claim_update(request, pk):
    """
    Update claim status and details (admin/staff only)
    """
    claim = get_object_or_404(InsuranceClaim, pk=pk)
    
    if request.method == 'POST':
        form = ClaimUpdateForm(request.POST, request.FILES, instance=claim)
        if form.is_valid():
            form.save()
            
            log_audit(request.user, 'update', 'InsuranceClaim', f'Updated claim: {claim.claim_number}')
            
            messages.success(request, f'Claim "{claim.claim_number}" updated successfully!')
            return redirect('insurance:claim_detail', pk=claim.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClaimUpdateForm(instance=claim)
    
    context = {
        'form': form,
        'claim': claim,
        'title': f'Update Claim: {claim.claim_number}',
        'button_text': 'Update Claim'
    }
    
    return render(request, 'insurance/claim_update_form.html', context)


# ==================== INSURANCE PAYMENT VIEWS ====================

@login_required
def payment_create(request, policy_pk):
    """
    Record an insurance premium payment
    """
    policy = get_object_or_404(InsurancePolicy, pk=policy_pk)
    
    if request.method == 'POST':
        form = InsurancePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.policy = policy
            payment.recorded_by = request.user
            payment.save()
            
            # Link to oldest unpaid schedule (if policy has payment plan)
            if policy.has_payment_plan:
                unpaid_schedule = policy.insurance_payment_schedules.filter(
                    is_paid=False
                ).order_by('installment_number').first()
                
                if unpaid_schedule:
                    unpaid_schedule.mark_as_paid(payment, amount=payment.amount)
            
            log_audit(
                request.user, 'create', 'InsurancePayment',
                f'Recorded payment {payment.receipt_number} for policy {policy.policy_number}'
            )
            
            messages.success(request, f'Payment recorded successfully! Receipt: {payment.receipt_number}')
            return redirect('insurance:policy_detail', pk=policy.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InsurancePaymentForm(initial={'policy': policy, 'amount': policy.premium_amount})
    
    context = {
        'form': form,
        'policy': policy,
        'today': timezone.now().date(),
        'title': f'Record Payment for Policy: {policy.policy_number}',
        'button_text': 'Record Payment'
    }

    return render(request, 'insurance/payment_form.html', context)


# ==================== REPORTING VIEWS ====================

@login_required
def insurance_dashboard(request):
    """
    Insurance analytics dashboard
    """
    today = timezone.now().date()
    
    # Policy statistics
    total_policies = InsurancePolicy.objects.count()
    active_policies = InsurancePolicy.objects.filter(status='active').count()
    expiring_30_days = InsurancePolicy.objects.filter(
        status='active',
        end_date__lte=today + timedelta(days=30),
        end_date__gte=today
    ).count()
    expired_policies = InsurancePolicy.objects.filter(status='expired').count()
    
    # Claim statistics
    total_claims = InsuranceClaim.objects.count()
    pending_claims = InsuranceClaim.objects.filter(
        status__in=['pending', 'under_review']
    ).count()
    
    # Financial statistics
    total_premium = InsurancePolicy.objects.filter(
        status='active'
    ).aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
    
    total_claimed = InsuranceClaim.objects.aggregate(
        Sum('claimed_amount')
    )['claimed_amount__sum'] or 0
    
    total_settled = InsuranceClaim.objects.filter(
        status='settled'
    ).aggregate(Sum('settled_amount'))['settled_amount__sum'] or 0
    
    # Recent activity
    recent_policies = InsurancePolicy.objects.select_related(
        'vehicle', 'provider'
    ).order_by('-created_at')[:5]
    
    recent_claims = InsuranceClaim.objects.select_related(
        'policy__vehicle'
    ).order_by('-claim_date')[:5]
    
    context = {
        'total_policies': total_policies,
        'active_policies': active_policies,
        'expiring_30_days': expiring_30_days,
        'expired_policies': expired_policies,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'total_premium': total_premium,
        'total_claimed': total_claimed,
        'total_settled': total_settled,
        'recent_policies': recent_policies,
        'recent_claims': recent_claims,
    }
    
    log_audit(request.user, 'view', 'Insurance', 'Viewed insurance dashboard')
    
    return render(request, 'insurance/dashboard.html', context)


@login_required
def generate_quote(request):
    """
    Generate insurance quote
    """
    if request.method == 'POST':
        form = InsuranceQuoteForm(request.POST)
        if form.is_valid():
            quote = form.calculate_quote()
            
            context = {
                'form': form,
                'quote': quote,
                'show_quote': True
            }
            
            log_audit(request.user, 'view', 'Insurance', 'Generated insurance quote')
            
            return render(request, 'insurance/generate_quote.html', context)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InsuranceQuoteForm()
    
    context = {
        'form': form,
        'show_quote': False
    }
    
    return render(request, 'insurance/generate_quote.html', context)


@login_required
def export_policies_csv(request):
    """
    Export policies to CSV
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="insurance_policies_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Policy Number', 'Vehicle', 'Provider', 'Client',
        'Policy Type', 'Start Date', 'End Date', 'Premium',
        'Sum Insured', 'Status'
    ])
    
    policies = InsurancePolicy.objects.select_related(
        'vehicle', 'provider', 'client'
    ).order_by('-start_date')
    
    for policy in policies:
        writer.writerow([
            policy.policy_number,
            str(policy.vehicle),
            policy.provider.name,
            policy.client.get_full_name() if policy.client else 'N/A',
            policy.get_policy_type_display(),
            policy.start_date.strftime('%Y-%m-%d'),
            policy.end_date.strftime('%Y-%m-%d'),
            policy.premium_amount,
            policy.sum_insured,
            policy.get_status_display()
        ])
    
    log_audit(request.user, 'export', 'InsurancePolicy', 'Exported policies to CSV')
    
    return response


@login_required
def export_claims_csv(request):
    """
    Export claims to CSV
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="insurance_claims_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Claim Number', 'Policy Number', 'Vehicle', 'Claim Type',
        'Incident Date', 'Claimed Amount', 'Approved Amount',
        'Settled Amount', 'Status'
    ])
    
    claims = InsuranceClaim.objects.select_related(
        'policy__vehicle'
    ).order_by('-claim_date')
    
    for claim in claims:
        writer.writerow([
            claim.claim_number,
            claim.policy.policy_number,
            str(claim.policy.vehicle),
            claim.get_claim_type_display(),
            claim.incident_date.strftime('%Y-%m-%d'),
            claim.claimed_amount,
            claim.approved_amount,
            claim.settled_amount,
            claim.get_status_display()
        ])
    
    log_audit(request.user, 'export', 'InsuranceClaim', 'Exported claims to CSV')
    
    return response


# ==================== AJAX/API VIEWS ====================

@login_required
def policy_stats_api(request):
    """
    API endpoint for policy statistics
    """
    status = request.GET.get('status', 'all')
    
    if status == 'active':
        policies = InsurancePolicy.objects.filter(status='active')
    elif status == 'expired':
        policies = InsurancePolicy.objects.filter(status='expired')
    else:
        policies = InsurancePolicy.objects.all()
    
    data = {
        'total': policies.count(),
        'by_type': {
            policy_type: policies.filter(policy_type=policy_type).count()
            for policy_type, _ in InsurancePolicy.POLICY_TYPE_CHOICES
        },
        'total_premium': float(policies.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0),
        'total_sum_insured': float(policies.aggregate(Sum('sum_insured'))['sum_insured__sum'] or 0),
    }
    
    return JsonResponse(data)


@login_required
def claim_stats_api(request):
    """
    API endpoint for claim statistics
    """
    period = request.GET.get('period', 'all')  # all, year, month
    
    claims = InsuranceClaim.objects.all()
    
    if period == 'year':
        claims = claims.filter(claim_date__year=timezone.now().year)
    elif period == 'month':
        now = timezone.now()
        claims = claims.filter(claim_date__year=now.year, claim_date__month=now.month)
    
    data = {
        'total': claims.count(),
        'by_status': {
            status: claims.filter(status=status).count()
            for status, _ in InsuranceClaim.STATUS_CHOICES
        },
        'by_type': {
            claim_type: claims.filter(claim_type=claim_type).count()
            for claim_type, _ in InsuranceClaim.CLAIM_TYPE_CHOICES
        },
        'total_claimed': float(claims.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0),
        'total_approved': float(claims.aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0),
        'total_settled': float(claims.aggregate(Sum('settled_amount'))['settled_amount__sum'] or 0),
    }
    
    return JsonResponse(data)


@login_required
def expiring_policies_api(request):
    """
    API endpoint for expiring policies data
    """
    days = int(request.GET.get('days', 30))
    
    today = timezone.now().date()
    expiring = InsurancePolicy.objects.filter(
        status='active',
        end_date__lte=today + timedelta(days=days),
        end_date__gte=today
    ).select_related('vehicle', 'client')
    
    policies_data = []
    for policy in expiring:
        policies_data.append({
            'id': policy.pk,
            'policy_number': policy.policy_number,
            'vehicle': str(policy.vehicle),
            'provider': policy.provider.name,
            'client': policy.client.get_full_name() if policy.client else 'N/A',
            'end_date': policy.end_date.strftime('%Y-%m-%d'),
            'days_until_expiry': policy.days_until_expiry,
            'premium': float(policy.premium_amount)
        })
    
    data = {
        'count': expiring.count(),
        'policies': policies_data
    }
    
    return JsonResponse(data)


@login_required
def send_bulk_reminders(request):
    """
    Send bulk expiry reminders
    """
    if request.method == 'POST':
        form = BulkPolicyReminderForm(request.POST)
        if form.is_valid():
            days_threshold = form.cleaned_data['days_threshold']
            reminder_type = form.cleaned_data['reminder_type']
            custom_message = form.cleaned_data.get('custom_message')
            
            # Get expiring policies
            today = timezone.now().date()
            expiring_policies = InsurancePolicy.objects.filter(
                status='active',
                end_date__lte=today + timedelta(days=days_threshold),
                end_date__gte=today,
                reminder_sent=False
            ).select_related('vehicle', 'client')
            
            sent_count = 0
            for policy in expiring_policies:
                # Prepare message
                if custom_message:
                    message = custom_message.format(
                        policy_number=policy.policy_number,
                        expiry_date=policy.end_date.strftime('%d/%m/%Y'),
                        vehicle=str(policy.vehicle)
                    )
                else:
                    message = (
                        f"Reminder: Your insurance policy {policy.policy_number} "
                        f"for {policy.vehicle} expires on {policy.end_date.strftime('%d/%m/%Y')}. "
                        f"Please renew to maintain coverage."
                    )
                
                # Send reminder (implement actual sending logic)
                if reminder_type in ['sms', 'both'] and policy.client:
                    # send_sms(policy.client.phone_primary, message)
                    pass
                
                if reminder_type in ['email', 'both'] and policy.client and policy.client.email:
                    # send_email(policy.client.email, 'Insurance Expiry Reminder', message)
                    pass
                
                # Mark reminder as sent
                policy.reminder_sent = True
                policy.reminder_sent_date = today
                policy.save()
                
                sent_count += 1
            
            log_audit(
                request.user, 'action', 'InsurancePolicy',
                f'Sent bulk reminders to {sent_count} policies'
            )
            
            messages.success(request, f'Reminders sent to {sent_count} policies!')
            return redirect('insurance:expiring_policies')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkPolicyReminderForm()
    
    context = {
        'form': form,
        'title': 'Send Bulk Expiry Reminders',
        'button_text': 'Send Reminders'
    }
    
    return render(request, 'insurance/send_bulk_reminders.html', context)


@login_required
def policy_comparison(request):
    """
    Compare multiple insurance policies
    """
    if request.method == 'POST':
        policy_ids = request.POST.getlist('policies')
        
        if len(policy_ids) < 2:
            messages.error(request, 'Please select at least 2 policies to compare.')
            return redirect('insurance:policy_list')
        
        if len(policy_ids) > 5:
            messages.error(request, 'You can compare a maximum of 5 policies at once.')
            return redirect('insurance:policy_list')
        
        policies = InsurancePolicy.objects.filter(
            pk__in=policy_ids
        ).select_related('vehicle', 'client')
        
        context = {
            'policies': policies
        }
        
        log_audit(request.user, 'view', 'InsurancePolicy', f'Compared {len(policy_ids)} policies')
        
        return render(request, 'insurance/policy_comparison.html', context)
    
    return redirect('insurance:policy_list')


@login_required
def claims_by_vehicle(request, vehicle_pk):
    """
    View all claims for a specific vehicle
    """
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    
    claims = InsuranceClaim.objects.filter(
        policy__vehicle=vehicle
    ).select_related('policy__vehicle').order_by('-claim_date')
    
    # Statistics
    total_claims = claims.count()
    total_claimed = claims.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    total_settled = claims.filter(status='settled').aggregate(
        Sum('settled_amount')
    )['settled_amount__sum'] or 0
    
    context = {
        'vehicle': vehicle,
        'claims': claims,
        'total_claims': total_claims,
        'total_claimed': total_claimed,
        'total_settled': total_settled,
    }
    
    log_audit(request.user, 'view', 'InsuranceClaim', f'Viewed claims for vehicle {vehicle}')
    
    return render(request, 'insurance/claims_by_vehicle.html', context)


@login_required
def claims_by_client(request, client_pk):
    """
    View all claims for a specific client
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    claims = InsuranceClaim.objects.filter(
        policy__client=client
    ).select_related('policy__vehicle', 'policy__client').order_by('-claim_date')
    
    # Statistics
    total_claims = claims.count()
    total_claimed = claims.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    total_settled = claims.filter(status='settled').aggregate(
        Sum('settled_amount')
    )['settled_amount__sum'] or 0
    
    context = {
        'client': client,
        'claims': claims,
        'total_claims': total_claims,
        'total_claimed': total_claimed,
        'total_settled': total_settled,
    }
    
    log_audit(request.user, 'view', 'InsuranceClaim', f'Viewed claims for client {client.get_full_name()}')
    
    return render(request, 'insurance/claims_by_client.html', context)


@login_required
def policies_by_vehicle(request, vehicle_pk):
    """
    View all policies for a specific vehicle
    """
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    
    policies = InsurancePolicy.objects.filter(
        vehicle=vehicle
    ).select_related('vehicle', 'client').order_by('-start_date')
    
    # Get current active policy
    active_policy = policies.filter(status='active').first()
    
    context = {
        'vehicle': vehicle,
        'policies': policies,
        'active_policy': active_policy,
        'total_policies': policies.count(),
    }
    
    log_audit(request.user, 'view', 'InsurancePolicy', f'Viewed policies for vehicle {vehicle}')
    
    return render(request, 'insurance/policies_by_vehicle.html', context)


@login_required
def policies_by_client(request, client_pk):
    """
    View all policies for a specific client
    """
    client = get_object_or_404(Client, pk=client_pk)
    
    policies = InsurancePolicy.objects.filter(
        client=client
    ).select_related('vehicle', 'client').order_by('-start_date')
    
    # Statistics
    total_policies = policies.count()
    active_policies = policies.filter(status='active').count()
    total_premium = policies.filter(status='active').aggregate(
        Sum('premium_amount')
    )['premium_amount__sum'] or 0
    
    context = {
        'client': client,
        'policies': policies,
        'total_policies': total_policies,
        'active_policies': active_policies,
        'total_premium': total_premium,
    }
    
    log_audit(request.user, 'view', 'InsurancePolicy', f'Viewed policies for client {client.get_full_name()}')
    
    return render(request, 'insurance/policies_by_client.html', context)


@login_required
def insurance_reports(request):
    """
    Insurance reports and analytics page
    """
    from apps.vehicles.models import TrackerAgent, TrackerRecord, ClearingAgent, ClearanceRecord
    from datetime import date

    # --- Date range ---
    preset = request.GET.get('preset', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    today = date.today()

    if preset == 'this_month':
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()
    elif preset == 'last_3_months':
        date_from = (today - timedelta(days=90)).isoformat()
        date_to = today.isoformat()
    elif preset == 'this_year':
        date_from = today.replace(month=1, day=1).isoformat()
        date_to = today.isoformat()

    policies = InsurancePolicy.objects.all()
    claims = InsuranceClaim.objects.all()

    if date_from:
        policies = policies.filter(start_date__gte=date_from)
        claims = claims.filter(claim_date__gte=date_from)
    if date_to:
        policies = policies.filter(start_date__lte=date_to)
        claims = claims.filter(claim_date__lte=date_to)

    # --- Top-level KPIs ---
    policy_agg = policies.aggregate(
        total_count=Count('id'),
        total_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        total_premium=Coalesce(Sum('premium_amount'), Value(0, output_field=DecimalField())),
        unpaid_buying=Coalesce(
            Sum('buying_price', filter=Q(dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    total_profit = policy_agg['total_selling'] - policy_agg['total_buying']
    profit_margin_pct = (
        round((total_profit / policy_agg['total_selling']) * 100, 1)
        if policy_agg['total_selling'] else 0
    )

    active_count = policies.filter(status='active').count()
    expired_count = policies.filter(status='expired').count()
    cancelled_count = policies.filter(status='cancelled').count()

    claim_agg = claims.aggregate(
        total_claims=Count('id'),
        total_claimed=Coalesce(Sum('claimed_amount'), Value(0, output_field=DecimalField())),
        total_approved=Coalesce(Sum('approved_amount'), Value(0, output_field=DecimalField())),
        total_settled=Coalesce(Sum('settled_amount'), Value(0, output_field=DecimalField())),
    )

    # --- Policy statistics by type ---
    policy_type_stats = []
    for policy_type, label in InsurancePolicy.POLICY_TYPE_CHOICES:
        qs = policies.filter(policy_type=policy_type)
        agg = qs.aggregate(
            count=Count('id'),
            total_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
            total_premium=Coalesce(Sum('premium_amount'), Value(0, output_field=DecimalField())),
        )
        profit = agg['total_selling'] - agg['total_buying']
        policy_type_stats.append({
            'type': label,
            'count': agg['count'],
            'total_buying': agg['total_buying'],
            'total_selling': agg['total_selling'],
            'total_premium': agg['total_premium'],
            'profit': profit,
        })

    # --- Policy status breakdown ---
    policy_status_stats = []
    for status_val, label in InsurancePolicy.STATUS_CHOICES:
        count = policies.filter(status=status_val).count()
        policy_status_stats.append({'status': label, 'value': status_val, 'count': count})

    # --- Claim statistics by type ---
    claim_type_stats = []
    for claim_type, label in InsuranceClaim.CLAIM_TYPE_CHOICES:
        qs = claims.filter(claim_type=claim_type)
        agg = qs.aggregate(
            count=Count('id'),
            total_claimed=Coalesce(Sum('claimed_amount'), Value(0, output_field=DecimalField())),
            total_approved=Coalesce(Sum('approved_amount'), Value(0, output_field=DecimalField())),
            total_settled=Coalesce(Sum('settled_amount'), Value(0, output_field=DecimalField())),
        )
        claim_type_stats.append({
            'type': label,
            'count': agg['count'],
            'total_claimed': agg['total_claimed'],
            'total_approved': agg['total_approved'],
            'total_settled': agg['total_settled'],
        })

    # --- Claim status breakdown ---
    claim_status_stats = []
    for status_val, label in InsuranceClaim.STATUS_CHOICES:
        count = claims.filter(status=status_val).count()
        claim_status_stats.append({'status': label, 'value': status_val, 'count': count})

    # --- Agent performance ---
    agent_stats = InsuranceAgent.objects.filter(is_active=True).annotate(
        policy_count=Count('policies'),
        total_buying=Coalesce(Sum('policies__buying_price'), Value(0, output_field=DecimalField())),
        total_selling=Coalesce(Sum('policies__selling_price'), Value(0, output_field=DecimalField())),
        total_owed_ann=Coalesce(
            Sum('policies__buying_price', filter=Q(policies__dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    ).order_by('-policy_count')[:15]

    # --- Tracker agent summary ---
    tracker_summary = TrackerAgent.objects.filter(is_active=True).annotate(
        record_count=Count('tracker_records'),
        total_buying=Coalesce(Sum('tracker_records__buying_price'), Value(0, output_field=DecimalField())),
        total_selling=Coalesce(Sum('tracker_records__selling_price'), Value(0, output_field=DecimalField())),
        total_owed_ann=Coalesce(
            Sum('tracker_records__buying_price',
                filter=Q(tracker_records__dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    ).order_by('-record_count')[:10]

    tracker_totals = TrackerRecord.objects.aggregate(
        grand_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        grand_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('buying_price', filter=Q(dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    )

    # --- Clearing agent summary ---
    clearing_summary = ClearingAgent.objects.filter(is_active=True).annotate(
        record_count=Count('clearance_records'),
        total_billed=Coalesce(Sum('clearance_records__amount'), Value(0, output_field=DecimalField())),
        total_owed_ann=Coalesce(
            Sum('clearance_records__amount',
                filter=Q(clearance_records__payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    ).order_by('-record_count')[:10]

    clearing_totals = ClearanceRecord.objects.aggregate(
        grand_billed=Coalesce(Sum('amount'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('amount', filter=Q(payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    )

    context = {
        # KPIs
        'total_count': policy_agg['total_count'],
        'total_buying': policy_agg['total_buying'],
        'total_selling': policy_agg['total_selling'],
        'total_premium': policy_agg['total_premium'],
        'total_profit': total_profit,
        'profit_margin_pct': profit_margin_pct,
        'unpaid_buying': policy_agg['unpaid_buying'],
        'active_count': active_count,
        'expired_count': expired_count,
        'cancelled_count': cancelled_count,
        # Claims KPIs
        'total_claims': claim_agg['total_claims'],
        'total_claimed': claim_agg['total_claimed'],
        'total_approved': claim_agg['total_approved'],
        'total_settled': claim_agg['total_settled'],
        # Breakdowns
        'policy_type_stats': policy_type_stats,
        'policy_status_stats': policy_status_stats,
        'claim_type_stats': claim_type_stats,
        'claim_status_stats': claim_status_stats,
        # Agents
        'agent_stats': agent_stats,
        # Tracker
        'tracker_summary': tracker_summary,
        'tracker_totals': tracker_totals,
        # Clearing
        'clearing_summary': clearing_summary,
        'clearing_totals': clearing_totals,
        # Filters
        'date_from': date_from,
        'date_to': date_to,
        'preset': preset,
    }

    log_audit(request.user, 'view', 'Insurance', 'Viewed insurance reports')
    return render(request, 'insurance/reports.html', context)


# ==================== INSURANCE AGENT LEDGER VIEWS ====================

@login_required
def agent_ledger_list(request):
    """List all insurance agents with their policy totals and outstanding balances."""
    from django.contrib import messages

    if request.method == 'POST':
        form = InsuranceAgentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insurance agent added successfully.')
            log_audit(request.user, 'create', 'InsuranceAgent', f'Added agent {form.cleaned_data["name"]}')
            return redirect('insurance:agent_ledger_list')
    else:
        form = InsuranceAgentForm()

    agents = InsuranceAgent.objects.filter(is_active=True).prefetch_related('policies').order_by('name')
    totals = InsurancePolicy.objects.aggregate(
        grand_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        grand_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('buying_price', filter=Q(dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    context = {
        'agents': agents,
        'grand_buying': totals['grand_buying'],
        'grand_selling': totals['grand_selling'],
        'grand_owed': totals['grand_owed'],
        'form': form,
    }
    log_audit(request.user, 'view', 'InsuranceAgent', 'Viewed insurance agent ledger')
    return render(request, 'insurance/agent_ledger_list.html', context)


@login_required
def agent_ledger_detail(request, pk):
    """Show all policies for an insurance agent and allow marking them paid."""
    agent = get_object_or_404(InsuranceAgent, pk=pk)
    policies = agent.policies.select_related('vehicle', 'client').order_by('-start_date')
    from .models import InsuranceAgentPayment
    payments = agent.payments.select_related('recorded_by').order_by('-payment_date')
    context = {
        'agent': agent,
        'policies': policies,
        'payments': payments,
    }
    log_audit(request.user, 'view', 'InsuranceAgent', f'Viewed ledger for agent {agent.name}')
    return render(request, 'insurance/agent_ledger_detail.html', context)


@login_required
def agent_ledger_mark_paid(request, pk):
    """Mark a single insurance policy as paid to the agent."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    policy = get_object_or_404(InsurancePolicy, pk=pk)
    policy.dealer_payment_status = 'paid'
    policy.save(update_fields=['dealer_payment_status'])
    log_audit(request.user, 'update', 'InsurancePolicy', f'Marked policy {policy.policy_number} as paid to agent')
    return JsonResponse({'status': 'paid', 'policy_id': pk})


@login_required
def agent_ledger_mark_all_paid(request, agent_pk):
    """Mark all unpaid policies for an agent as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    agent = get_object_or_404(InsuranceAgent, pk=agent_pk)
    updated = agent.policies.filter(dealer_payment_status='unpaid').update(dealer_payment_status='paid')
    log_audit(request.user, 'update', 'InsuranceAgent', f'Marked all {updated} unpaid policies as paid for agent {agent.name}')
    return JsonResponse({'status': 'ok', 'updated': updated})


@login_required
def record_insurance_agent_payment(request, agent_pk):
    """Record a lump-sum payment to an insurance agent."""
    from django.views.decorators.http import require_POST
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('insurance:agent_ledger_detail', pk=agent_pk)
    agent = get_object_or_404(InsuranceAgent, pk=agent_pk)
    from .models import InsuranceAgentPayment
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid payment amount.')
        return redirect('insurance:agent_ledger_detail', pk=agent_pk)
    from datetime import date as date_type
    payment_date = date_type.today()
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    with transaction.atomic():
        InsuranceAgentPayment.objects.create(
            agent=agent,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=payment_date,
            recorded_by=request.user,
        )

        # Mark unpaid policies as paid (oldest first) until payment is exhausted
        remaining = amount
        unpaid_policies = agent.policies.filter(
            dealer_payment_status='unpaid'
        ).order_by('start_date', 'created_at')

        policies_cleared = 0
        for policy in unpaid_policies:
            if remaining >= policy.buying_price:
                remaining -= policy.buying_price
                policy.dealer_payment_status = 'paid'
                policy.save(update_fields=['dealer_payment_status'])
                policies_cleared += 1
            else:
                break

    if policies_cleared:
        messages.success(
            request,
            f'Payment of KES {amount:,.2f} recorded for {agent.name}. '
            f'{policies_cleared} policy/policies marked as settled.'
        )
    else:
        messages.success(request, f'Payment of KES {amount:,.2f} recorded for {agent.name}.')
    return redirect('insurance:agent_ledger_detail', pk=agent_pk)