"""
Utility functions for the repossessions app.
Handles repossession logic, calculations, notifications, and reporting.
"""

from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta, date
from decimal import Decimal
import csv
from io import StringIO


# ============================================================================
# Repossession Detection and Initiation
# ============================================================================

def identify_defaulted_clients(grace_period_days=30, min_missed_payments=2):
    """
    Identify clients who are in default and eligible for repossession.
    
    Args:
        grace_period_days: Days after missed payment before flagging
        min_missed_payments: Minimum number of missed payments
    
    Returns:
        QuerySet of clients eligible for repossession
    """
    from apps.clients.models import Client
    from apps.payments.models import Payment
    
    cutoff_date = date.today() - timedelta(days=grace_period_days)
    
    # Find clients with overdue payments
    clients_with_defaults = Client.objects.annotate(
        missed_payments=Count(
            'payments',
            filter=Q(
                payments__status='OVERDUE',
                payments__due_date__lt=cutoff_date
            )
        ),
        total_overdue=Sum(
            'payments__amount',
            filter=Q(
                payments__status='OVERDUE',
                payments__due_date__lt=cutoff_date
            )
        )
    ).filter(
        missed_payments__gte=min_missed_payments
    )
    
    return clients_with_defaults


def calculate_outstanding_amount(client):
    """
    Calculate total outstanding amount for a client.
    """
    from apps.payments.models import Payment
    
    overdue = Payment.objects.filter(
        client=client,
        status='OVERDUE'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    return overdue


def auto_initiate_repossession(client, vehicle, reason='PAYMENT_DEFAULT'):
    """
    Automatically initiate repossession for a client.
    """
    from .models import Repossession
    
    # Check if repossession already exists
    existing = Repossession.objects.filter(
        vehicle=vehicle,
        client=client,
        status__in=['PENDING', 'NOTICE_SENT', 'IN_PROGRESS', 'VEHICLE_RECOVERED']
    ).exists()
    
    if existing:
        return None, "Repossession already in progress"
    
    # Calculate details
    outstanding = calculate_outstanding_amount(client)
    missed_payments = count_missed_payments(client)
    last_payment = get_last_payment_date(client)
    
    # Create repossession
    repossession = Repossession.objects.create(
        vehicle=vehicle,
        client=client,
        reason=reason,
        outstanding_amount=outstanding,
        payments_missed=missed_payments,
        last_payment_date=last_payment,
        initiated_date=date.today(),
        status='PENDING'
    )
    
    return repossession, "Repossession initiated successfully"


def count_missed_payments(client):
    """
    Count number of missed payments for a client.
    """
    from apps.payments.models import Payment
    
    return Payment.objects.filter(
        client=client,
        status='OVERDUE'
    ).count()


def get_last_payment_date(client):
    """
    Get date of last payment made by client.
    """
    from apps.payments.models import Payment
    
    last_payment = Payment.objects.filter(
        client=client,
        status='PAID'
    ).order_by('-payment_date').first()
    
    return last_payment.payment_date if last_payment else None


# ============================================================================
# Cost Calculations
# ============================================================================

def calculate_total_repossession_cost(repossession):
    """
    Calculate total cost of repossession including all expenses.
    """
    from .models import RepossessionExpense
    
    # Get expenses
    expenses = RepossessionExpense.objects.filter(
        repossession=repossession
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Direct costs from repossession model
    direct_costs = (
        repossession.recovery_cost +
        repossession.storage_cost +
        repossession.legal_cost +
        repossession.other_costs
    )
    
    return expenses + direct_costs


def calculate_recovery_roi(repossession):
    """
    Calculate return on investment for recovery.
    
    Returns:
        dict with costs, recovery amount, and ROI percentage
    """
    total_cost = calculate_total_repossession_cost(repossession)
    
    # Amount recovered (if vehicle was auctioned or client paid)
    if repossession.resolution_type == 'PAID_IN_FULL':
        recovered = repossession.outstanding_amount
    elif repossession.resolution_type == 'AUCTIONED':
        # Would need auction sale price - placeholder
        recovered = repossession.outstanding_amount * Decimal('0.7')  # Assume 70% recovery
    else:
        recovered = Decimal('0.00')
    
    net_recovery = recovered - total_cost
    roi_percentage = (net_recovery / total_cost * 100) if total_cost > 0 else 0
    
    return {
        'total_cost': total_cost,
        'amount_recovered': recovered,
        'net_recovery': net_recovery,
        'roi_percentage': round(roi_percentage, 2)
    }


def estimate_storage_cost(days, daily_rate=Decimal('50.00')):
    """
    Estimate storage cost based on days.
    """
    return days * daily_rate


# ============================================================================
# Notice Generation
# ============================================================================

def generate_repossession_notice(repossession, notice_type='FIRST_NOTICE'):
    """
    Generate repossession notice content.
    """
    client = repossession.client
    vehicle = repossession.vehicle
    
    notice_templates = {
        'FIRST_NOTICE': f"""
NOTICE OF INTENT TO REPOSSESS

Dear {client.name},

This is to inform you that your account is currently in default with {repossession.payments_missed} missed payment(s).

Outstanding Amount: KES {repossession.outstanding_amount:,.2f}
Last Payment Date: {repossession.last_payment_date or 'N/A'}

Vehicle Details:
- Make/Model: {vehicle.make} {vehicle.model}
- Registration: {vehicle.registration_number}

You have 14 days from the date of this notice to bring your account current or contact us to make payment arrangements. Failure to respond will result in repossession of the vehicle.

Please contact us immediately at [CONTACT INFO]

Date: {date.today().strftime('%B %d, %Y')}
        """,
        
        'FINAL_NOTICE': f"""
FINAL NOTICE OF REPOSSESSION

Dear {client.name},

This is your FINAL NOTICE regarding the default on your account.

Outstanding Amount: KES {repossession.outstanding_amount:,.2f}
Days Overdue: {repossession.get_days_in_process()}

Despite previous communications, your account remains in default. You have 7 days from the date of this notice to settle the outstanding amount or make satisfactory payment arrangements.

Failure to respond will result in immediate repossession of:
{vehicle.make} {vehicle.model} - {vehicle.registration_number}

This is your last opportunity to resolve this matter without legal action.

Date: {date.today().strftime('%B %d, %Y')}
        """,
        
        'LEGAL_NOTICE': f"""
LEGAL NOTICE OF REPOSSESSION

To: {client.name}

Take notice that pursuant to the terms of your financing agreement and applicable laws, we hereby notify you of our intention to repossess the following vehicle:

Make/Model: {vehicle.make} {vehicle.model}
Registration: {vehicle.registration_number}
Outstanding Amount: KES {repossession.outstanding_amount:,.2f}

This action is being taken due to default on payment obligations. You have breached the terms of the agreement by failing to make required payments.

Legal proceedings will commence if payment is not received within 7 days.

Date: {date.today().strftime('%B %d, %Y')}
        """
    }
    
    return notice_templates.get(notice_type, notice_templates['FIRST_NOTICE'])


def send_repossession_notice_email(repossession, notice_type='FIRST_NOTICE'):
    """
    Send repossession notice via email.
    """
    client = repossession.client
    
    if not client.email:
        return False, "Client email not available"
    
    content = generate_repossession_notice(repossession, notice_type)
    
    subject_map = {
        'FIRST_NOTICE': 'Notice of Intent to Repossess',
        'SECOND_NOTICE': 'Second Notice - Account in Default',
        'FINAL_NOTICE': 'FINAL NOTICE - Immediate Action Required',
        'LEGAL_NOTICE': 'Legal Notice of Repossession',
        'COURT_SUMMONS': 'Court Summons - Repossession Proceedings',
    }
    
    subject = subject_map.get(notice_type, 'Repossession Notice')
    
    try:
        send_mail(
            subject,
            content,
            settings.DEFAULT_FROM_EMAIL,
            [client.email],
            fail_silently=False,
        )
        return True, "Email sent successfully"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


# ============================================================================
# Status and Workflow Management
# ============================================================================

def get_next_recommended_action(repossession):
    """
    Recommend next action based on current status.
    """
    status_actions = {
        'PENDING': 'Send first notice to client',
        'NOTICE_SENT': 'Wait for response or send follow-up notice',
        'IN_PROGRESS': 'Coordinate recovery attempt with agent',
        'VEHICLE_RECOVERED': 'Assess vehicle condition and store securely',
        'ON_HOLD': 'Review reason for hold and determine next steps',
    }
    
    # Check specific conditions
    if repossession.status == 'NOTICE_SENT':
        # Check if notices are overdue
        overdue_notices = repossession.notices.filter(
            response_deadline__lt=date.today(),
            response_received=False
        ).count()
        
        if overdue_notices > 0:
            return 'Send final notice or initiate recovery'
    
    return status_actions.get(repossession.status, 'Review repossession status')


def calculate_repossession_timeline(repossession):
    """
    Calculate expected timeline milestones.
    """
    initiated = repossession.initiated_date
    
    timeline = {
        'initiated': initiated,
        'first_notice_due': initiated + timedelta(days=3),
        'response_deadline': initiated + timedelta(days=17),
        'final_notice_due': initiated + timedelta(days=20),
        'recovery_target': initiated + timedelta(days=30),
        'expected_completion': initiated + timedelta(days=45),
    }
    
    # Calculate if milestones are met or overdue
    today = date.today()
    for key, milestone_date in timeline.items():
        if key == 'initiated':
            continue
        
        timeline[f'{key}_status'] = 'upcoming' if milestone_date > today else 'overdue'
    
    return timeline


def check_compliance_requirements(repossession):
    """
    Check if all compliance requirements are met.
    """
    issues = []
    
    # Check notices sent
    if not repossession.legal_notice_sent:
        issues.append('Legal notice not sent')
    
    # Check documentation
    required_docs = ['NOTICE', 'LEGAL_LETTER']
    uploaded_doc_types = repossession.documents.values_list('document_type', flat=True)
    
    for doc_type in required_docs:
        if doc_type not in uploaded_doc_types:
            issues.append(f'Missing document: {doc_type}')
    
    # Check if client was contacted
    if not repossession.contacts.exists():
        issues.append('No contact attempts recorded')
    
    # Check grace period
    if repossession.get_days_in_process() < 14:
        issues.append('Minimum 14-day grace period not elapsed')
    
    return {
        'compliant': len(issues) == 0,
        'issues': issues
    }


# ============================================================================
# Reporting and Analytics
# ============================================================================

def generate_repossession_summary(start_date=None, end_date=None):
    """
    Generate summary statistics for repossessions.
    """
    from .models import Repossession
    
    repos = Repossession.objects.all()
    
    if start_date:
        repos = repos.filter(initiated_date__gte=start_date)
    if end_date:
        repos = repos.filter(initiated_date__lte=end_date)
    
    summary = {
        'total_repossessions': repos.count(),
        'by_status': {},
        'by_reason': {},
        'total_outstanding': repos.aggregate(
            Sum('outstanding_amount')
        )['outstanding_amount__sum'] or Decimal('0.00'),
        'total_costs': repos.aggregate(
            Sum('total_cost')
        )['total_cost__sum'] or Decimal('0.00'),
        'average_days': 0,
        'completion_rate': 0,
    }
    
    # By status
    for status, label in Repossession.STATUS_CHOICES:
        count = repos.filter(status=status).count()
        summary['by_status'][label] = count
    
    # By reason
    for reason, label in Repossession.REASON_CHOICES:
        count = repos.filter(reason=reason).count()
        summary['by_reason'][label] = count
    
    # Average days
    completed = repos.filter(status='COMPLETED')
    if completed.exists():
        total_days = sum([r.get_days_in_process() for r in completed])
        summary['average_days'] = round(total_days / completed.count(), 1)
    
    # Completion rate
    if repos.count() > 0:
        completed_count = completed.count()
        summary['completion_rate'] = round(
            (completed_count / repos.count()) * 100, 1
        )
    
    return summary


def export_repossessions_to_csv(queryset):
    """
    Export repossessions to CSV format.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Repossession Number', 'Vehicle', 'Client', 'Status', 'Reason',
        'Outstanding Amount', 'Total Cost', 'Initiated Date',
        'Days in Process', 'Assigned To', 'Resolution'
    ])
    
    # Data
    for repo in queryset:
        writer.writerow([
            repo.repossession_number,
            str(repo.vehicle),
            repo.client.name if hasattr(repo.client, 'name') else str(repo.client),
            repo.get_status_display(),
            repo.get_reason_display(),
            repo.outstanding_amount,
            repo.total_cost,
            repo.initiated_date.strftime('%Y-%m-%d'),
            repo.get_days_in_process(),
            repo.assigned_to.get_full_name() if repo.assigned_to else '',
            repo.get_resolution_type_display() if repo.resolution_type else ''
        ])
    
    return output.getvalue()


def generate_agent_performance_report(agent, start_date=None, end_date=None):
    """
    Generate performance report for a recovery agent.
    """
    from .models import Repossession, RepossessionRecoveryAttempt
    
    assigned = Repossession.objects.filter(assigned_to=agent)
    
    if start_date:
        assigned = assigned.filter(initiated_date__gte=start_date)
    if end_date:
        assigned = assigned.filter(initiated_date__lte=end_date)
    
    # Recovery attempts
    attempts = RepossessionRecoveryAttempt.objects.filter(
        created_by=agent
    )
    
    if start_date:
        attempts = attempts.filter(attempt_date__gte=start_date)
    if end_date:
        attempts = attempts.filter(attempt_date__lte=end_date)
    
    successful = attempts.filter(result='SUCCESSFUL').count()
    total_attempts = attempts.count()
    
    report = {
        'agent': agent.get_full_name(),
        'assigned_cases': assigned.count(),
        'completed_cases': assigned.filter(status='COMPLETED').count(),
        'recovery_attempts': total_attempts,
        'successful_recoveries': successful,
        'success_rate': round(
            (successful / total_attempts * 100) if total_attempts > 0 else 0, 1
        ),
        'average_days_to_recovery': 0,
    }
    
    # Average days
    completed = assigned.filter(status='COMPLETED', recovery_date__isnull=False)
    if completed.exists():
        total_days = sum([
            (r.recovery_date - r.initiated_date).days for r in completed
        ])
        report['average_days_to_recovery'] = round(total_days / completed.count(), 1)
    
    return report


# ============================================================================
# Notification Utilities
# ============================================================================

def notify_repossession_team(repossession, event_type):
    """
    Send notification to repossession team about events.
    """
    subject_map = {
        'initiated': f'New Repossession: {repossession.repossession_number}',
        'recovered': f'Vehicle Recovered: {repossession.repossession_number}',
        'completed': f'Repossession Completed: {repossession.repossession_number}',
        'overdue': f'OVERDUE: {repossession.repossession_number}',
    }
    
    subject = subject_map.get(event_type, 'Repossession Update')
    
    message = f"""
Repossession Update: {repossession.repossession_number}

Vehicle: {repossession.vehicle}
Client: {repossession.client}
Status: {repossession.get_status_display()}
Outstanding: KES {repossession.outstanding_amount:,.2f}
Days in Process: {repossession.get_days_in_process()}

Assigned To: {repossession.assigned_to.get_full_name() if repossession.assigned_to else 'Unassigned'}

View Details: [LINK TO REPOSSESSION]
    """
    
    # Get team emails
    team_emails = []
    if repossession.assigned_to and repossession.assigned_to.email:
        team_emails.append(repossession.assigned_to.email)
    
    # Add manager emails
    from django.contrib.auth import get_user_model
    User = get_user_model()
    managers = User.objects.filter(is_staff=True, is_active=True)
    team_emails.extend(managers.values_list('email', flat=True))
    
    if team_emails:
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                team_emails,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending team notification: {e}")


def send_recovery_success_notification(repossession):
    """
    Send notification when vehicle is successfully recovered.
    """
    notify_repossession_team(repossession, 'recovered')
    
    # Also notify finance team about recovery
    message = f"""
Vehicle Successfully Recovered

Repossession: {repossession.repossession_number}
Vehicle: {repossession.vehicle}
Client: {repossession.client}
Outstanding Amount: KES {repossession.outstanding_amount:,.2f}
Recovery Date: {repossession.recovery_date}
Location: {repossession.current_location}

Next Steps: Assess vehicle condition and determine resolution strategy.
    """
    
    # Send to finance team
    # Implementation depends on your user/role structure


# ============================================================================
# Vehicle Condition Assessment
# ============================================================================

def assess_vehicle_value(vehicle):
    """
    Estimate current value of repossessed vehicle.
    Placeholder - would integrate with valuation service.
    """
    # This would typically integrate with external valuation APIs
    # For now, return a simplified estimate
    
    from datetime import date
    
    if not vehicle.purchase_price:
        return None
    
    # Simple depreciation: 15% per year
    age_years = (date.today() - vehicle.purchase_date).days / 365 if vehicle.purchase_date else 0
    depreciation_factor = (0.85 ** age_years)
    
    estimated_value = vehicle.purchase_price * Decimal(str(depreciation_factor))
    
    return {
        'estimated_value': round(estimated_value, 2),
        'original_price': vehicle.purchase_price,
        'age_years': round(age_years, 1),
        'depreciation_rate': round((1 - depreciation_factor) * 100, 1)
    }


# ============================================================================
# Dashboard Statistics
# ============================================================================

def get_repossession_dashboard_stats():
    """
    Get statistics for repossession dashboard.
    """
    from .models import Repossession, RepossessionNotice
    
    stats = {
        'total_active': Repossession.objects.exclude(
            status__in=['COMPLETED', 'CANCELLED']
        ).count(),
        'pending_approval': Repossession.objects.filter(status='PENDING').count(),
        'in_recovery': Repossession.objects.filter(status='IN_PROGRESS').count(),
        'vehicles_recovered': Repossession.objects.filter(status='VEHICLE_RECOVERED').count(),
        'overdue_notices': RepossessionNotice.objects.filter(
            response_deadline__lt=date.today(),
            response_received=False
        ).count(),
    }
    
    # Financial stats
    active_repos = Repossession.objects.exclude(status__in=['COMPLETED', 'CANCELLED'])
    stats['total_outstanding'] = active_repos.aggregate(
        Sum('outstanding_amount')
    )['outstanding_amount__sum'] or Decimal('0.00')
    
    stats['total_recovery_costs'] = active_repos.aggregate(
        Sum('total_cost')
    )['total_cost__sum'] or Decimal('0.00')
    
    return stats