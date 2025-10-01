"""
Utility functions for the payments app
Includes PDF generation, calculations, and helper functions
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import io

# PDF Generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas


# ==================== CALCULATION UTILITIES ====================

def calculate_monthly_installment(total_amount, deposit, months, interest_rate=0):
    """
    Calculate monthly installment amount including interest
    
    Args:
        total_amount (Decimal): Total purchase price
        deposit (Decimal): Down payment
        months (int): Number of months for payment
        interest_rate (Decimal): Annual interest rate percentage
    
    Returns:
        dict: Dictionary with calculation details
    """
    balance = total_amount - deposit
    
    if interest_rate and interest_rate > 0:
        # Calculate simple interest
        interest_amount = balance * (interest_rate / 100) * (months / 12)
        total_with_interest = balance + interest_amount
    else:
        interest_amount = Decimal('0.00')
        total_with_interest = balance
    
    monthly_installment = total_with_interest / months
    
    return {
        'balance_after_deposit': balance,
        'interest_amount': interest_amount,
        'total_with_interest': total_with_interest,
        'monthly_installment': monthly_installment,
        'total_to_pay': total_amount + interest_amount,
        'interest_rate': interest_rate
    }


def calculate_amortization_schedule(principal, annual_rate, months):
    """
    Calculate loan amortization schedule with compound interest
    
    Args:
        principal (Decimal): Loan principal amount
        annual_rate (Decimal): Annual interest rate percentage
        months (int): Number of months
    
    Returns:
        list: List of payment details for each month
    """
    if annual_rate == 0:
        # Simple equal payments with no interest
        monthly_payment = principal / months
        schedule = []
        remaining_balance = principal
        
        for month in range(1, months + 1):
            schedule.append({
                'month': month,
                'payment': monthly_payment,
                'principal': monthly_payment,
                'interest': Decimal('0.00'),
                'balance': remaining_balance - monthly_payment
            })
            remaining_balance -= monthly_payment
        
        return schedule
    
    # Calculate monthly payment using compound interest formula
    monthly_rate = (annual_rate / 100) / 12
    monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / \
                     ((1 + monthly_rate) ** months - 1)
    
    schedule = []
    remaining_balance = principal
    
    for month in range(1, months + 1):
        interest_payment = remaining_balance * monthly_rate
        principal_payment = monthly_payment - interest_payment
        remaining_balance -= principal_payment
        
        schedule.append({
            'month': month,
            'payment': monthly_payment,
            'principal': principal_payment,
            'interest': interest_payment,
            'balance': max(remaining_balance, Decimal('0.00'))
        })
    
    return schedule


def calculate_payment_progress(total_amount, amount_paid):
    """
    Calculate payment progress percentage
    
    Args:
        total_amount (Decimal): Total amount to be paid
        amount_paid (Decimal): Amount already paid
    
    Returns:
        Decimal: Progress percentage (0-100)
    """
    if total_amount <= 0:
        return Decimal('0.00')
    
    progress = (amount_paid / total_amount) * 100
    return min(progress, Decimal('100.00'))


def calculate_late_fee(amount_due, days_overdue, rate_per_day=0.1):
    """
    Calculate late payment fee
    
    Args:
        amount_due (Decimal): Amount that is overdue
        days_overdue (int): Number of days overdue
        rate_per_day (float): Daily late fee rate percentage
    
    Returns:
        Decimal: Late fee amount
    """
    if days_overdue <= 0:
        return Decimal('0.00')
    
    # Calculate late fee (e.g., 0.1% per day)
    late_fee = amount_due * (Decimal(str(rate_per_day)) / 100) * days_overdue
    
    # Cap late fee at 50% of amount due
    max_fee = amount_due * Decimal('0.5')
    return min(late_fee, max_fee)


def format_currency(amount, currency='KES'):
    """
    Format amount as currency string
    
    Args:
        amount (Decimal): Amount to format
        currency (str): Currency code
    
    Returns:
        str: Formatted currency string
    """
    return f"{currency} {amount:,.2f}"


# ==================== DATE UTILITIES ====================

def get_next_payment_date(start_date, months_offset):
    """
    Calculate next payment date from start date
    
    Args:
        start_date (date): Starting date
        months_offset (int): Number of months to add
    
    Returns:
        date: Next payment date
    """
    return start_date + relativedelta(months=months_offset)


def get_payment_due_dates(start_date, number_of_installments):
    """
    Generate list of payment due dates
    
    Args:
        start_date (date): First payment date
        number_of_installments (int): Total number of installments
    
    Returns:
        list: List of due dates
    """
    due_dates = []
    current_date = start_date
    
    for i in range(number_of_installments):
        due_dates.append(current_date)
        current_date = current_date + relativedelta(months=1)
    
    return due_dates


def is_payment_overdue(due_date):
    """
    Check if payment is overdue
    
    Args:
        due_date (date): Payment due date
    
    Returns:
        bool: True if overdue
    """
    return timezone.now().date() > due_date


def days_until_due(due_date):
    """
    Calculate days until payment is due
    
    Args:
        due_date (date): Payment due date
    
    Returns:
        int: Days until due (negative if overdue)
    """
    delta = due_date - timezone.now().date()
    return delta.days


# ==================== PDF GENERATION UTILITIES ====================

def generate_payment_receipt_pdf(payment):
    """
    Generate PDF receipt for a payment
    
    Args:
        payment: Payment instance
    
    Returns:
        HttpResponse: PDF response
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
    )
    
    # Title
    elements.append(Paragraph("PAYMENT RECEIPT", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Receipt details
    receipt_data = [
        ['Receipt Number:', payment.receipt_number],
        ['Date:', payment.payment_date.strftime('%d %B %Y')],
        ['Payment Method:', payment.get_payment_method_display()],
        ['Transaction Ref:', payment.transaction_reference or 'N/A'],
    ]
    
    receipt_table = Table(receipt_data, colWidths=[2*inch, 3*inch])
    receipt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(receipt_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Client & Vehicle details
    elements.append(Paragraph("Client Information", heading_style))
    client = payment.client_vehicle.client
    client_data = [
        ['Name:', client.get_full_name()],
        ['ID Number:', client.id_number],
        ['Phone:', client.phone_primary],
    ]
    
    client_table = Table(client_data, colWidths=[2*inch, 3*inch])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Vehicle details
    elements.append(Paragraph("Vehicle Information", heading_style))
    vehicle = payment.client_vehicle.vehicle
    vehicle_data = [
        ['Vehicle:', f"{vehicle.make} {vehicle.model} {vehicle.year}"],
        ['Registration:', vehicle.registration_number],
    ]
    
    vehicle_table = Table(vehicle_data, colWidths=[2*inch, 3*inch])
    vehicle_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment summary
    elements.append(Paragraph("Payment Summary", heading_style))
    cv = payment.client_vehicle
    summary_data = [
        ['Purchase Price:', format_currency(cv.purchase_price)],
        ['Total Paid:', format_currency(cv.total_paid)],
        ['This Payment:', format_currency(payment.amount)],
        ['Balance:', format_currency(cv.balance)],
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.black),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_text = "Thank you for your payment!"
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Create response
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number}.pdf"'
    
    return response


def generate_agreement_pdf(client_vehicle):
    """
    Generate sales agreement PDF
    
    Args:
        client_vehicle: ClientVehicle instance
    
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
        spaceAfter=30
    )
    
    elements.append(Paragraph("VEHICLE SALES AGREEMENT", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Agreement date
    date_text = f"Date: {timezone.now().strftime('%d %B %Y')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Parties
    client = client_vehicle.client
    vehicle = client_vehicle.vehicle
    
    seller_text = """
    <b>SELLER:</b><br/>
    [Company Name]<br/>
    [Company Address]<br/>
    [Company Phone]<br/>
    """
    elements.append(Paragraph(seller_text, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    buyer_text = f"""
    <b>BUYER:</b><br/>
    {client.get_full_name()}<br/>
    ID No: {client.id_number}<br/>
    Phone: {client.phone_primary}<br/>
    Address: {client.physical_address}<br/>
    """
    elements.append(Paragraph(buyer_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Vehicle details
    elements.append(Paragraph("<b>VEHICLE DETAILS:</b>", styles['Heading2']))
    vehicle_info = [
        ['Make & Model:', f"{vehicle.make} {vehicle.model}"],
        ['Year:', str(vehicle.year)],
        ['Registration:', vehicle.registration_number],
        ['VIN/Chassis:', vehicle.vin or 'N/A'],
        ['Color:', vehicle.color or 'N/A'],
    ]
    
    vehicle_table = Table(vehicle_info, colWidths=[2*inch, 4*inch])
    vehicle_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment terms
    elements.append(Paragraph("<b>PAYMENT TERMS:</b>", styles['Heading2']))
    payment_info = [
        ['Purchase Price:', format_currency(client_vehicle.purchase_price)],
        ['Deposit Paid:', format_currency(client_vehicle.deposit_paid)],
        ['Balance:', format_currency(client_vehicle.balance)],
        ['Monthly Installment:', format_currency(client_vehicle.monthly_installment)],
        ['Number of Months:', str(client_vehicle.installment_months)],
        ['Interest Rate:', f"{client_vehicle.interest_rate}%"],
    ]
    
    payment_table = Table(payment_info, colWidths=[2*inch, 4*inch])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Terms and conditions
    elements.append(Paragraph("<b>TERMS AND CONDITIONS:</b>", styles['Heading2']))
    terms = """
    1. The buyer agrees to pay the balance in monthly installments as specified above.<br/>
    2. Late payments will attract a penalty fee.<br/>
    3. The vehicle remains the property of the seller until full payment is made.<br/>
    4. The buyer is responsible for insurance and maintenance of the vehicle.<br/>
    5. Default in payment may result in repossession of the vehicle.<br/>
    """
    elements.append(Paragraph(terms, styles['Normal']))
    elements.append(Spacer(1, 0.5*inch))
    
    # Signatures
    signature_data = [
        ['_____________________', '_____________________'],
        ['Seller Signature', 'Buyer Signature'],
        ['', ''],
        ['Date: ______________', 'Date: ______________'],
    ]
    
    signature_table = Table(signature_data, colWidths=[3*inch, 3*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(signature_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="agreement_{client.id_number}.pdf"'
    
    return response


def generate_payment_tracker_pdf(client_vehicle):
    """
    Generate payment tracker/history PDF
    
    Args:
        client_vehicle: ClientVehicle instance
    
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
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    elements.append(Paragraph("PAYMENT TRACKER", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Client and vehicle info
    client = client_vehicle.client
    vehicle = client_vehicle.vehicle
    
    info_text = f"""
    <b>Client:</b> {client.get_full_name()} (ID: {client.id_number})<br/>
    <b>Vehicle:</b> {vehicle.make} {vehicle.model} ({vehicle.registration_number})<br/>
    <b>Generated:</b> {timezone.now().strftime('%d %B %Y')}
    """
    elements.append(Paragraph(info_text, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Payment summary
    summary_data = [
        ['Purchase Price:', format_currency(client_vehicle.purchase_price)],
        ['Deposit Paid:', format_currency(client_vehicle.deposit_paid)],
        ['Total Paid:', format_currency(client_vehicle.total_paid)],
        ['Balance:', format_currency(client_vehicle.balance)],
        ['Payment Progress:', f"{client_vehicle.payment_progress:.1f}%"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment history
    from .models import Payment
    payments = Payment.objects.filter(client_vehicle=client_vehicle).order_by('payment_date')
    
    if payments.exists():
        elements.append(Paragraph("<b>PAYMENT HISTORY:</b>", styles['Heading2']))
        
        payment_data = [['Date', 'Receipt No.', 'Method', 'Amount', 'Balance']]
        
        for payment in payments:
            payment_data.append([
                payment.payment_date.strftime('%d/%m/%Y'),
                payment.receipt_number,
                payment.get_payment_method_display(),
                format_currency(payment.amount),
                format_currency(client_vehicle.balance)  # This should ideally be the balance at that time
            ])
        
        payment_table = Table(payment_data, colWidths=[1.2*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (3, 1), (4, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))
        elements.append(payment_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payment_tracker_{client.id_number}.pdf"'
    
    return response


def generate_performa_invoice_pdf(client_vehicle):
    """
    Generate performa invoice PDF
    
    Args:
        client_vehicle: ClientVehicle instance
    
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
    
    elements.append(Paragraph("PROFORMA INVOICE", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Invoice details
    invoice_no = f"INV-{timezone.now().strftime('%Y%m%d')}-{client_vehicle.pk}"
    date_text = f"<b>Invoice No:</b> {invoice_no}<br/><b>Date:</b> {timezone.now().strftime('%d %B %Y')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Bill to
    client = client_vehicle.client
    bill_to = f"""
    <b>BILL TO:</b><br/>
    {client.get_full_name()}<br/>
    ID: {client.id_number}<br/>
    Phone: {client.phone_primary}<br/>
    {client.physical_address}
    """
    elements.append(Paragraph(bill_to, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Vehicle details table
    vehicle = client_vehicle.vehicle
    vehicle_data = [
        ['Description', 'Amount'],
        [f"{vehicle.make} {vehicle.model} {vehicle.year}\nReg: {vehicle.registration_number}", 
         format_currency(client_vehicle.purchase_price)]
    ]
    
    vehicle_table = Table(vehicle_data, colWidths=[4*inch, 2*inch])
    vehicle_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Totals
    totals_data = [
        ['Subtotal:', format_currency(client_vehicle.purchase_price)],
        ['Deposit:', f"({format_currency(client_vehicle.deposit_paid)})"],
        ['<b>Balance Due:</b>', f"<b>{format_currency(client_vehicle.balance)}</b>"],
    ]
    
    totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment terms
    terms_text = f"""
    <b>PAYMENT TERMS:</b><br/>
    Monthly Installment: {format_currency(client_vehicle.monthly_installment)}<br/>
    Number of Installments: {client_vehicle.installment_months} months<br/>
    Interest Rate: {client_vehicle.interest_rate}% per annum
    """
    elements.append(Paragraph(terms_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer_text = "<i>This is a proforma invoice and not a tax invoice.</i>"
    elements.append(Paragraph(footer_text, styles['Italic']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="proforma_invoice_{invoice_no}.pdf"'
    
    return response


# ==================== NOTIFICATION UTILITIES ====================

def send_payment_reminder_sms(client, amount_due, due_date):
    """
    Send payment reminder via SMS
    
    Args:
        client: Client instance
        amount_due (Decimal): Amount due
        due_date (date): Payment due date
    
    Returns:
        bool: Success status
    """
    # Integration with SMS service (Twilio, Africa's Talking, etc.)
    message = (
        f"Dear {client.get_full_name()}, "
        f"your payment of {format_currency(amount_due)} is due on {due_date.strftime('%d/%m/%Y')}. "
        f"Please make payment to avoid penalties."
    )
    
    # TODO: Implement actual SMS sending
    # Example with Twilio:
    # from twilio.rest import Client
    # twilio_client = Client(account_sid, auth_token)
    # twilio_client.messages.create(
    #     to=client.phone_primary,
    #     from_=twilio_number,
    #     body=message
    # )
    
    return True


def send_payment_confirmation_email(payment):
    """
    Send payment confirmation email
    
    Args:
        payment: Payment instance
    
    Returns:
        bool: Success status
    """
    from django.core.mail import send_mail
    
    client = payment.client_vehicle.client
    
    subject = f"Payment Receipt - {payment.receipt_number}"
    message = f"""
    Dear {client.get_full_name()},
    
    Thank you for your payment!
    
    Receipt Number: {payment.receipt_number}
    Amount Paid: {format_currency(payment.amount)}
    Payment Date: {payment.payment_date.strftime('%d %B %Y')}
    Payment Method: {payment.get_payment_method_display()}
    
    Remaining Balance: {format_currency(payment.client_vehicle.balance)}
    
    Best regards,
    [Company Name]
    """
    
    try:
        send_mail(
            subject,
            message,
            'noreply@company.com',
            [client.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


# ==================== VALIDATION UTILITIES ====================

def validate_payment_amount(amount, remaining_balance):
    """
    Validate payment amount
    
    Args:
        amount (Decimal): Payment amount
        remaining_balance (Decimal): Current balance
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if amount <= 0:
        return False, "Payment amount must be greater than zero"
    
    if amount > remaining_balance:
        return False, f"Payment amount ({format_currency(amount)}) exceeds remaining balance ({format_currency(remaining_balance)})"
    
    return True, None


def validate_installment_plan(total_amount, deposit, monthly_installment, months, interest_rate=0):
    """
    Validate installment plan parameters
    
    Args:
        total_amount (Decimal): Total purchase price
        deposit (Decimal): Down payment
        monthly_installment (Decimal): Monthly payment amount
        months (int): Number of months
        interest_rate (Decimal): Interest rate percentage
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if deposit >= total_amount:
        return False, "Deposit must be less than total amount"
    
    if months < 1:
        return False, "Number of months must be at least 1"
    
    if months > 120:
        return False, "Number of months cannot exceed 120 (10 years)"
    
    if interest_rate < 0 or interest_rate > 100:
        return False, "Interest rate must be between 0 and 100"
    
    # Calculate expected monthly payment
    calculation = calculate_monthly_installment(total_amount, deposit, months, interest_rate)
    expected_monthly = calculation['monthly_installment']
    
    # Allow 1 KES tolerance for rounding
    difference = abs(monthly_installment - expected_monthly)
    if difference > 1:
        return False, f"Monthly installment ({format_currency(monthly_installment)}) doesn't match calculated amount ({format_currency(expected_monthly)})"
    
    return True, None


# ==================== REPORTING UTILITIES ====================

def generate_payment_summary_report(start_date, end_date):
    """
    Generate payment summary report for a date range
    
    Args:
        start_date (date): Start date
        end_date (date): End date
    
    Returns:
        dict: Report data
    """
    from .models import Payment
    from django.db.models import Sum, Count, Avg
    
    payments = Payment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date
    )
    
    summary = {
        'total_payments': payments.count(),
        'total_amount': payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00'),
        'average_payment': payments.aggregate(Avg('amount'))['amount__avg'] or Decimal('0.00'),
        'by_method': {},
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Breakdown by payment method
    for method, label in Payment.PAYMENT_METHOD_CHOICES:
        method_payments = payments.filter(payment_method=method)
        summary['by_method'][method] = {
            'label': label,
            'count': method_payments.count(),
            'amount': method_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        }
    
    return summary


def get_overdue_report():
    """
    Generate report of overdue payments
    
    Returns:
        dict: Overdue report data
    """
    from .models import PaymentSchedule
    from django.db.models import Sum, Count
    
    today = timezone.now().date()
    
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    )
    
    report = {
        'total_overdue_schedules': overdue_schedules.count(),
        'total_overdue_amount': overdue_schedules.aggregate(
            Sum('amount_due')
        )['amount_due__sum'] or Decimal('0.00'),
        'overdue_by_days': {},
        'schedules': overdue_schedules
    }
    
    # Categorize by days overdue
    for schedule in overdue_schedules:
        days = schedule.days_overdue
        if days <= 7:
            category = '1-7 days'
        elif days <= 30:
            category = '8-30 days'
        elif days <= 60:
            category = '31-60 days'
        else:
            category = '60+ days'
        
        if category not in report['overdue_by_days']:
            report['overdue_by_days'][category] = {
                'count': 0,
                'amount': Decimal('0.00')
            }
        
        report['overdue_by_days'][category]['count'] += 1
        report['overdue_by_days'][category]['amount'] += schedule.remaining_amount
    
    return report


def get_defaulters_list():
    """
    Get list of clients with overdue payments
    
    Returns:
        list: List of defaulter data
    """
    from .models import PaymentSchedule
    from apps.clients.models import Client
    
    today = timezone.now().date()
    
    # Get all overdue schedules
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    ).select_related(
        'installment_plan__client_vehicle__client',
        'installment_plan__client_vehicle__vehicle'
    )
    
    # Group by client
    defaulters = {}
    for schedule in overdue_schedules:
        client = schedule.installment_plan.client_vehicle.client
        
        if client.id not in defaulters:
            defaulters[client.id] = {
                'client': client,
                'overdue_schedules': [],
                'total_overdue_amount': Decimal('0.00'),
                'oldest_overdue_date': schedule.due_date,
                'days_overdue': schedule.days_overdue
            }
        
        defaulters[client.id]['overdue_schedules'].append(schedule)
        defaulters[client.id]['total_overdue_amount'] += schedule.remaining_amount
        
        # Track oldest overdue date
        if schedule.due_date < defaulters[client.id]['oldest_overdue_date']:
            defaulters[client.id]['oldest_overdue_date'] = schedule.due_date
            defaulters[client.id]['days_overdue'] = schedule.days_overdue
    
    # Convert to list and sort by days overdue
    defaulters_list = list(defaulters.values())
    defaulters_list.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    return defaulters_list


def get_collection_efficiency(start_date, end_date):
    """
    Calculate collection efficiency for a period
    
    Args:
        start_date (date): Start date
        end_date (date): End date
    
    Returns:
        dict: Collection efficiency metrics
    """
    from .models import Payment, PaymentSchedule
    from django.db.models import Sum
    
    # Total payments collected
    payments_collected = Payment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Total amount due in this period
    schedules_due = PaymentSchedule.objects.filter(
        due_date__gte=start_date,
        due_date__lte=end_date
    ).aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
    
    # Calculate efficiency percentage
    if schedules_due > 0:
        efficiency = (payments_collected / schedules_due) * 100
    else:
        efficiency = Decimal('0.00')
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'payments_collected': payments_collected,
        'amount_due': schedules_due,
        'efficiency_percentage': efficiency,
        'shortfall': schedules_due - payments_collected
    }


# ==================== EXPORT UTILITIES ====================

def export_payments_to_csv(payments, filename='payments.csv'):
    """
    Export payments to CSV
    
    Args:
        payments: QuerySet of payments
        filename (str): Output filename
    
    Returns:
        HttpResponse: CSV response
    """
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Receipt Number', 'Date', 'Client', 'ID Number', 
        'Vehicle', 'Amount', 'Payment Method', 
        'Transaction Reference', 'Balance', 'Recorded By'
    ])
    
    for payment in payments:
        writer.writerow([
            payment.receipt_number,
            payment.payment_date.strftime('%Y-%m-%d'),
            payment.client_vehicle.client.get_full_name(),
            payment.client_vehicle.client.id_number,
            str(payment.client_vehicle.vehicle),
            payment.amount,
            payment.get_payment_method_display(),
            payment.transaction_reference or '',
            payment.client_vehicle.balance,
            payment.recorded_by.get_full_name() if payment.recorded_by else ''
        ])
    
    return response


def export_payment_schedules_to_csv(schedules, filename='payment_schedules.csv'):
    """
    Export payment schedules to CSV
    
    Args:
        schedules: QuerySet of payment schedules
        filename (str): Output filename
    
    Returns:
        HttpResponse: CSV response
    """
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Client', 'Vehicle', 'Installment Number', 
        'Due Date', 'Amount Due', 'Amount Paid', 
        'Remaining', 'Status', 'Days Overdue'
    ])
    
    for schedule in schedules:
        client = schedule.installment_plan.client_vehicle.client
        vehicle = schedule.installment_plan.client_vehicle.vehicle
        
        status = 'Paid' if schedule.is_paid else ('Overdue' if schedule.is_overdue else 'Pending')
        
        writer.writerow([
            client.get_full_name(),
            str(vehicle),
            schedule.installment_number,
            schedule.due_date.strftime('%Y-%m-%d'),
            schedule.amount_due,
            schedule.amount_paid,
            schedule.remaining_amount,
            status,
            schedule.days_overdue if schedule.is_overdue else 0
        ])
    
    return response


# ==================== DASHBOARD UTILITIES ====================

def get_payment_dashboard_data():
    """
    Get data for payment dashboard
    
    Returns:
        dict: Dashboard data
    """
    from .models import Payment, InstallmentPlan, PaymentSchedule
    from django.db.models import Sum, Count
    
    today = timezone.now().date()
    this_month = timezone.now()
    
    # This month statistics
    this_month_payments = Payment.objects.filter(
        payment_date__year=this_month.year,
        payment_date__month=this_month.month
    )
    
    # Overdue statistics
    overdue_schedules = PaymentSchedule.objects.filter(
        is_paid=False,
        due_date__lt=today
    )
    
    # Active plans
    active_plans = InstallmentPlan.objects.filter(
        is_active=True,
        is_completed=False
    )
    
    dashboard_data = {
        # This month
        'this_month_payments': this_month_payments.count(),
        'this_month_amount': this_month_payments.aggregate(
            Sum('amount')
        )['amount__sum'] or Decimal('0.00'),
        
        # Overdue
        'overdue_count': overdue_schedules.count(),
        'overdue_amount': overdue_schedules.aggregate(
            Sum('amount_due')
        )['amount_due__sum'] or Decimal('0.00'),
        
        # Active plans
        'active_plans_count': active_plans.count(),
        
        # Due this month
        'due_this_month': PaymentSchedule.objects.filter(
            is_paid=False,
            due_date__year=this_month.year,
            due_date__month=this_month.month
        ).count(),
        
        # Recent payments (last 5)
        'recent_payments': Payment.objects.select_related(
            'client_vehicle__client',
            'client_vehicle__vehicle'
        ).order_by('-payment_date')[:5],
    }
    
    return dashboard_data


# ==================== NUMBER FORMATTING UTILITIES ====================

def format_number(number, decimal_places=2):
    """
    Format number with commas and decimal places
    
    Args:
        number: Number to format
        decimal_places (int): Number of decimal places
    
    Returns:
        str: Formatted number
    """
    if decimal_places == 0:
        return f"{number:,.0f}"
    elif decimal_places == 2:
        return f"{number:,.2f}"
    else:
        return f"{number:,.{decimal_places}f}"


def number_to_words(amount):
    """
    Convert number to words (for checks/receipts)
    
    Args:
        amount (Decimal): Amount to convert
    
    Returns:
        str: Amount in words
    """
    # Simple implementation for Kenyan Shillings
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 
             'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    
    def convert_below_thousand(n):
        if n == 0:
            return ''
        elif n < 10:
            return ones[n]
        elif n < 20:
            return teens[n - 10]
        elif n < 100:
            return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')
        else:
            return ones[n // 100] + ' Hundred' + (' and ' + convert_below_thousand(n % 100) if n % 100 != 0 else '')
    
    if amount == 0:
        return 'Zero Shillings'
    
    num = int(amount)
    cents = int((amount - num) * 100)
    
    if num >= 1000000:
        millions = num // 1000000
        remainder = num % 1000000
        result = convert_below_thousand(millions) + ' Million'
        if remainder > 0:
            result += ' ' + convert_below_thousand(remainder)
    elif num >= 1000:
        thousands = num // 1000
        remainder = num % 1000
        result = convert_below_thousand(thousands) + ' Thousand'
        if remainder > 0:
            result += ' ' + convert_below_thousand(remainder)
    else:
        result = convert_below_thousand(num)
    
    result += ' Shillings'
    
    if cents > 0:
        result += ' and ' + convert_below_thousand(cents) + ' Cents'
    
    return result + ' Only'


# ==================== PAYMENT STATUS UTILITIES ====================

def get_payment_status_color(status):
    """
    Get color code for payment status
    
    Args:
        status (str): Payment status
    
    Returns:
        str: Hex color code
    """
    colors = {
        'paid': '#28a745',      # Green
        'pending': '#ffc107',   # Yellow
        'overdue': '#dc3545',   # Red
        'partial': '#17a2b8',   # Cyan
    }
    return colors.get(status, '#6c757d')  # Default gray


def get_payment_status_badge(schedule):
    """
    Get HTML badge for payment schedule status
    
    Args:
        schedule: PaymentSchedule instance
    
    Returns:
        str: HTML badge string
    """
    if schedule.is_paid:
        status = 'paid'
        label = 'PAID'
    elif schedule.is_overdue:
        status = 'overdue'
        label = f'OVERDUE ({schedule.days_overdue} days)'
    elif schedule.is_partial_payment:
        status = 'partial'
        label = 'PARTIAL'
    else:
        status = 'pending'
        label = 'PENDING'
    
    color = get_payment_status_color(status)
    
    return f'<span style="background-color: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{label}</span>'