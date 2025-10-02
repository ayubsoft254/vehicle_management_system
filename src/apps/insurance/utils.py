"""
Utility functions for the insurance app
Includes reminder sending, PDF generation, and helper functions
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import HttpResponse
from decimal import Decimal
from datetime import date, timedelta
import io

# PDF Generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# ==================== REMINDER UTILITIES ====================

def send_expiry_reminder_sms(policy):
    """
    Send SMS reminder for policy expiry
    
    Args:
        policy: InsurancePolicy instance
    
    Returns:
        bool: Success status
    """
    if not policy.client or not policy.client.phone_primary:
        return False
    
    days_left = policy.days_until_expiry
    
    message = (
        f"Reminder: Your insurance policy {policy.policy_number} "
        f"for {policy.vehicle} expires in {days_left} days on "
        f"{policy.end_date.strftime('%d/%m/%Y')}. "
        f"Please renew to maintain coverage. "
        f"Contact {policy.provider.name} at {policy.provider.phone_primary}."
    )
    
    # TODO: Integrate with SMS service (Twilio, Africa's Talking, etc.)
    # Example:
    # from twilio.rest import Client
    # client = Client(account_sid, auth_token)
    # client.messages.create(
    #     to=policy.client.phone_primary,
    #     from_=twilio_number,
    #     body=message
    # )
    
    print(f"SMS sent to {policy.client.phone_primary}: {message}")
    return True


def send_expiry_reminder_email(policy):
    """
    Send email reminder for policy expiry
    
    Args:
        policy: InsurancePolicy instance
    
    Returns:
        bool: Success status
    """
    if not policy.client or not policy.client.email:
        return False
    
    days_left = policy.days_until_expiry
    
    subject = f"Insurance Expiry Reminder - Policy {policy.policy_number}"
    
    message = f"""
    Dear {policy.client.get_full_name()},
    
    This is a reminder that your insurance policy is expiring soon.
    
    Policy Details:
    - Policy Number: {policy.policy_number}
    - Vehicle: {policy.vehicle}
    - Provider: {policy.provider.name}
    - Expiry Date: {policy.end_date.strftime('%d %B %Y')}
    - Days Remaining: {days_left} days
    
    Please renew your policy to maintain continuous coverage.
    
    Contact Details:
    {policy.provider.name}
    Phone: {policy.provider.phone_primary}
    Email: {policy.provider.email or 'N/A'}
    
    Best regards,
    Vehicle Management System
    """
    
    try:
        send_mail(
            subject,
            message,
            'noreply@company.com',
            [policy.client.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


def send_claim_update_notification(claim, update_type='status_change'):
    """
    Send notification about claim status update
    
    Args:
        claim: InsuranceClaim instance
        update_type: Type of update (status_change, approved, rejected, settled)
    
    Returns:
        bool: Success status
    """
    if not claim.client or not claim.client.email:
        return False
    
    subject_map = {
        'status_change': f"Claim Status Update - {claim.claim_number}",
        'approved': f"Claim Approved - {claim.claim_number}",
        'rejected': f"Claim Rejected - {claim.claim_number}",
        'settled': f"Claim Settled - {claim.claim_number}",
    }
    
    subject = subject_map.get(update_type, f"Claim Update - {claim.claim_number}")
    
    message = f"""
    Dear {claim.client.get_full_name()},
    
    Your insurance claim has been updated.
    
    Claim Details:
    - Claim Number: {claim.claim_number}
    - Vehicle: {claim.vehicle}
    - Claim Type: {claim.get_claim_type_display()}
    - Status: {claim.get_status_display()}
    - Claimed Amount: KES {claim.claimed_amount:,.2f}
    """
    
    if claim.approved_amount > 0:
        message += f"- Approved Amount: KES {claim.approved_amount:,.2f}\n"
    
    if claim.settled_amount > 0:
        message += f"- Settled Amount: KES {claim.settled_amount:,.2f}\n"
    
    if claim.rejection_reason:
        message += f"\nRejection Reason:\n{claim.rejection_reason}\n"
    
    message += """
    
    For more information, please contact your insurance provider.
    
    Best regards,
    Vehicle Management System
    """
    
    try:
        send_mail(
            subject,
            message,
            'noreply@company.com',
            [claim.client.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


def get_expiring_policies(days=30):
    """
    Get policies expiring within specified days
    
    Args:
        days: Number of days to look ahead
    
    Returns:
        QuerySet: Expiring policies
    """
    from .models import InsurancePolicy
    
    today = timezone.now().date()
    future_date = today + timedelta(days=days)
    
    return InsurancePolicy.objects.filter(
        status='active',
        end_date__range=[today, future_date],
        reminder_sent=False
    ).select_related('vehicle', 'provider', 'client')


def send_bulk_expiry_reminders(days=30, method='both'):
    """
    Send bulk expiry reminders
    
    Args:
        days: Days threshold for expiry
        method: 'sms', 'email', or 'both'
    
    Returns:
        dict: Statistics of sent reminders
    """
    policies = get_expiring_policies(days)
    
    stats = {
        'total': policies.count(),
        'sms_sent': 0,
        'email_sent': 0,
        'failed': 0
    }
    
    for policy in policies:
        success = False
        
        if method in ['sms', 'both']:
            if send_expiry_reminder_sms(policy):
                stats['sms_sent'] += 1
                success = True
        
        if method in ['email', 'both']:
            if send_expiry_reminder_email(policy):
                stats['email_sent'] += 1
                success = True
        
        if success:
            # Mark reminder as sent
            policy.reminder_sent = True
            policy.reminder_sent_date = timezone.now().date()
            policy.save()
        else:
            stats['failed'] += 1
    
    return stats


# ==================== CALCULATION UTILITIES ====================

def calculate_premium_estimate(vehicle_value, policy_type, vehicle_age=0, driver_age=None, has_claims=False):
    """
    Calculate estimated insurance premium
    
    Args:
        vehicle_value: Value of the vehicle
        policy_type: Type of coverage (comprehensive, third_party, etc.)
        vehicle_age: Age of vehicle in years
        driver_age: Age of driver
        has_claims: Whether there's claims history
    
    Returns:
        dict: Premium calculation breakdown
    """
    # Base rates
    base_rates = {
        'comprehensive': Decimal('0.05'),  # 5%
        'third_party_fire_theft': Decimal('0.03'),  # 3%
        'third_party': Decimal('0.02'),  # 2%
    }
    
    base_rate = base_rates.get(policy_type, Decimal('0.03'))
    base_premium = vehicle_value * base_rate
    
    adjustments = []
    final_premium = base_premium
    
    # Vehicle age adjustment
    if vehicle_age > 10:
        adjustment = base_premium * Decimal('0.20')  # +20%
        final_premium += adjustment
        adjustments.append({
            'factor': 'Vehicle Age (>10 years)',
            'percentage': 20,
            'amount': adjustment
        })
    
    # Driver age adjustment
    if driver_age:
        if driver_age < 25:
            adjustment = base_premium * Decimal('0.30')  # +30%
            final_premium += adjustment
            adjustments.append({
                'factor': 'Young Driver (<25 years)',
                'percentage': 30,
                'amount': adjustment
            })
        elif driver_age > 65:
            adjustment = base_premium * Decimal('0.15')  # +15%
            final_premium += adjustment
            adjustments.append({
                'factor': 'Senior Driver (>65 years)',
                'percentage': 15,
                'amount': adjustment
            })
    
    # Claims history adjustment
    if has_claims:
        adjustment = base_premium * Decimal('0.25')  # +25%
        final_premium += adjustment
        adjustments.append({
            'factor': 'Claims History',
            'percentage': 25,
            'amount': adjustment
        })
    
    return {
        'vehicle_value': vehicle_value,
        'policy_type': policy_type,
        'base_rate': float(base_rate * 100),  # As percentage
        'base_premium': base_premium,
        'adjustments': adjustments,
        'total_adjustments': sum(adj['amount'] for adj in adjustments),
        'final_premium': final_premium
    }


def calculate_pro_rata_refund(policy, cancellation_date):
    """
    Calculate pro-rata refund for cancelled policy
    
    Args:
        policy: InsurancePolicy instance
        cancellation_date: Date of cancellation
    
    Returns:
        Decimal: Refund amount
    """
    total_days = (policy.end_date - policy.start_date).days
    used_days = (cancellation_date - policy.start_date).days
    remaining_days = max(0, total_days - used_days)
    
    if total_days == 0:
        return Decimal('0.00')
    
    refund = (policy.premium_amount / total_days) * remaining_days
    
    # Apply administrative fee (10% of refund)
    admin_fee = refund * Decimal('0.10')
    final_refund = refund - admin_fee
    
    return max(Decimal('0.00'), final_refund)


def get_claim_approval_rate(provider=None, claim_type=None):
    """
    Calculate claim approval rate
    
    Args:
        provider: InsuranceProvider instance (optional)
        claim_type: Type of claim (optional)
    
    Returns:
        dict: Approval statistics
    """
    from .models import InsuranceClaim
    
    claims = InsuranceClaim.objects.all()
    
    if provider:
        claims = claims.filter(policy__provider=provider)
    
    if claim_type:
        claims = claims.filter(claim_type=claim_type)
    
    total = claims.count()
    approved = claims.filter(status__in=['approved', 'settled']).count()
    rejected = claims.filter(status='rejected').count()
    pending = claims.filter(status__in=['pending', 'under_review']).count()
    
    approval_rate = (approved / total * 100) if total > 0 else 0
    rejection_rate = (rejected / total * 100) if total > 0 else 0
    
    return {
        'total_claims': total,
        'approved': approved,
        'rejected': rejected,
        'pending': pending,
        'approval_rate': approval_rate,
        'rejection_rate': rejection_rate
    }


# ==================== PDF GENERATION UTILITIES ====================

def generate_policy_certificate_pdf(policy):
    """
    Generate insurance policy certificate PDF
    
    Args:
        policy: InsurancePolicy instance
    
    Returns:
        HttpResponse: PDF response
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor('#1e40af'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    elements.append(Paragraph("INSURANCE CERTIFICATE", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Policy details
    policy_data = [
        ['Policy Number:', policy.policy_number],
        ['Policy Type:', policy.get_policy_type_display()],
        ['Status:', policy.get_status_display()],
        ['Start Date:', policy.start_date.strftime('%d %B %Y')],
        ['End Date:', policy.end_date.strftime('%d %B %Y')],
    ]
    
    policy_table = Table(policy_data, colWidths=[2.5*inch, 4*inch])
    policy_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(policy_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Insured details
    elements.append(Paragraph("<b>INSURED DETAILS:</b>", styles['Heading2']))
    
    if policy.client:
        insured_data = [
            ['Name:', policy.client.get_full_name()],
            ['ID Number:', policy.client.id_number],
            ['Phone:', policy.client.phone_primary],
            ['Address:', policy.client.physical_address],
        ]
    else:
        insured_data = [['Name:', 'Not specified']]
    
    insured_table = Table(insured_data, colWidths=[2.5*inch, 4*inch])
    insured_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(insured_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Vehicle details
    elements.append(Paragraph("<b>VEHICLE DETAILS:</b>", styles['Heading2']))
    vehicle_data = [
        ['Make & Model:', f"{policy.vehicle.make} {policy.vehicle.model}"],
        ['Year:', str(policy.vehicle.year)],
        ['Registration:', policy.vehicle.registration_number],
        ['VIN/Chassis:', policy.vehicle.vin or 'N/A'],
    ]
    
    vehicle_table = Table(vehicle_data, colWidths=[2.5*inch, 4*inch])
    vehicle_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Coverage details
    elements.append(Paragraph("<b>COVERAGE DETAILS:</b>", styles['Heading2']))
    coverage_data = [
        ['Premium Amount:', f"KES {policy.premium_amount:,.2f}"],
        ['Sum Insured:', f"KES {policy.sum_insured:,.2f}"],
        ['Excess Amount:', f"KES {policy.excess_amount:,.2f}"],
    ]
    
    coverage_table = Table(coverage_data, colWidths=[2.5*inch, 4*inch])
    coverage_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
    ]))
    elements.append(coverage_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Provider details
    elements.append(Paragraph("<b>INSURANCE PROVIDER:</b>", styles['Heading2']))
    provider_text = f"""
    {policy.provider.name}<br/>
    Phone: {policy.provider.phone_primary}<br/>
    Email: {policy.provider.email or 'N/A'}<br/>
    {policy.provider.physical_address}
    """
    elements.append(Paragraph(provider_text, styles['Normal']))
    elements.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_text = f"<i>Certificate issued on {timezone.now().strftime('%d %B %Y')}</i>"
    elements.append(Paragraph(footer_text, styles['Italic']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{policy.policy_number}.pdf"'
    
    return response


def generate_claim_report_pdf(claim):
    """
    Generate insurance claim report PDF
    
    Args:
        claim: InsuranceClaim instance
    
    Returns:
        HttpResponse: PDF response
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#1e40af'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    elements.append(Paragraph("INSURANCE CLAIM REPORT", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Claim details
    claim_data = [
        ['Claim Number:', claim.claim_number],
        ['Status:', claim.get_status_display()],
        ['Claim Type:', claim.get_claim_type_display()],
        ['Claim Date:', claim.claim_date.strftime('%d %B %Y')],
        ['Incident Date:', claim.incident_date.strftime('%d %B %Y')],
    ]
    
    claim_table = Table(claim_data, colWidths=[2.5*inch, 4*inch])
    claim_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(claim_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Policy & Vehicle
    elements.append(Paragraph("<b>POLICY & VEHICLE:</b>", styles['Heading2']))
    policy_vehicle_data = [
        ['Policy Number:', claim.policy.policy_number],
        ['Vehicle:', str(claim.vehicle)],
        ['Provider:', claim.provider.name],
    ]
    
    pv_table = Table(policy_vehicle_data, colWidths=[2.5*inch, 4*inch])
    pv_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(pv_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Incident details
    elements.append(Paragraph("<b>INCIDENT DETAILS:</b>", styles['Heading2']))
    incident_text = f"""
    <b>Location:</b> {claim.incident_location}<br/>
    <b>Description:</b><br/>
    {claim.incident_description}
    """
    elements.append(Paragraph(incident_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Financial summary
    elements.append(Paragraph("<b>FINANCIAL SUMMARY:</b>", styles['Heading2']))
    financial_data = [
        ['Claimed Amount:', f"KES {claim.claimed_amount:,.2f}"],
        ['Approved Amount:', f"KES {claim.approved_amount:,.2f}"],
        ['Settled Amount:', f"KES {claim.settled_amount:,.2f}"],
        ['Excess Paid:', f"KES {claim.excess_paid:,.2f}"],
    ]
    
    financial_table = Table(financial_data, colWidths=[2.5*inch, 4*inch])
    financial_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
    ]))
    elements.append(financial_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="claim_{claim.claim_number}.pdf"'
    
    return response


# ==================== VALIDATION UTILITIES ====================

def validate_policy_dates(start_date, end_date):
    """
    Validate insurance policy dates
    
    Args:
        start_date: Policy start date
        end_date: Policy end date
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if end_date <= start_date:
        return False, "End date must be after start date"
    
    duration = (end_date - start_date).days
    if duration > 730:  # 2 years
        return False, "Policy duration cannot exceed 2 years"
    
    if duration < 30:  # 1 month
        return False, "Policy duration must be at least 30 days"
    
    return True, None


def validate_claim_amount(claimed_amount, sum_insured):
    """
    Validate claim amount against sum insured
    
    Args:
        claimed_amount: Amount being claimed
        sum_insured: Policy sum insured
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if claimed_amount <= 0:
        return False, "Claim amount must be greater than zero"
    
    if claimed_amount > sum_insured:
        return False, f"Claim amount (KES {claimed_amount:,.2f}) cannot exceed sum insured (KES {sum_insured:,.2f})"
    
    return True, None


# ==================== FORMAT UTILITIES ====================

def format_currency(amount, currency='KES'):
    """
    Format amount as currency string
    
    Args:
        amount: Amount to format
        currency: Currency code
    
    Returns:
        str: Formatted currency string
    """
    return f"{currency} {amount:,.2f}"


def get_policy_status_color(status):
    """
    Get color code for policy status
    
    Args:
        status: Policy status
    
    Returns:
        str: Hex color code
    """
    colors_map = {
        'active': '#28a745',
        'expired': '#dc3545',
        'cancelled': '#6c757d',
        'renewed': '#007bff',
    }
    return colors_map.get(status, '#6c757d')


def get_claim_status_color(status):
    """
    Get color code for claim status
    
    Args:
        status: Claim status
    
    Returns:
        str: Hex color code
    """
    colors_map = {
        'pending': '#ffc107',
        'under_review': '#007bff',
        'approved': '#28a745',
        'rejected': '#dc3545',
        'settled': '#17a2b8',
    }
    return colors_map.get(status, '#6c757d')