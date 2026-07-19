"""
Sales Agreement PDF Generator
Generates a PDF sales agreement with auto-filled vehicle and client information
"""
from io import BytesIO
import base64
import json
from datetime import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image,
    HRFlowable, KeepTogether,
)
from reportlab.lib import colors
from django.utils import timezone

from utils.letterhead import draw_letterhead_footer, FOOTER_RESERVED_HEIGHT


def generate_sales_agreement_pdf(client_vehicle, snapshot=None, paybill=None):
    """
    Generate a PDF sales agreement for a vehicle purchase

    Args:
        client_vehicle: ClientVehicle instance
        snapshot: optional frozen agreement data dict
        paybill: paybill number to print on payment page (defaults to settings.MPESA_SHORTCODE)

    Returns:
        BytesIO object containing the PDF
    """
    if paybill is None:
        try:
            from django.conf import settings
            paybill = settings.MPESA_SHORTCODE or '4320049'
        except Exception:
            paybill = '4320049'
    buffer = BytesIO()

    _title_reg = (snapshot or {}).get('vehicle', {}).get('registration_number') or client_vehicle.vehicle.registration_number or ''

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=FOOTER_RESERVED_HEIGHT + 0.1*inch,
        title=f"Sales Agreement - {_title_reg}"
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    normal_small = ParagraphStyle(
        'CustomSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=9,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )

    # Build the content
    elements = []

    if snapshot:
        from types import SimpleNamespace
        from datetime import datetime as _snap_dt
        sv = snapshot.get('vehicle', {})
        sc = snapshot.get('client', {})
        sp = snapshot.get('purchase', {})
        _fn = sc.get('full_name', '')
        vehicle = SimpleNamespace(
            make=sv.get('make', ''),
            model=sv.get('model', ''),
            registration_number=sv.get('registration_number', ''),
            vin=sv.get('vin', ''),
            engine_number=sv.get('engine_number', ''),
            fuel_type=sv.get('fuel_type', ''),
            engine_size=sv.get('engine_size', ''),
            color=sv.get('color', ''),
            year=sv.get('year', ''),
        )
        client = SimpleNamespace(
            get_full_name=lambda: _fn,
            phone_primary=sc.get('phone_primary', ''),
            id_number=sc.get('id_number', ''),
            kra_pin=sc.get('kra_pin', ''),
            email=sc.get('email', ''),
            postal_address=sc.get('postal_address', ''),
            city=sc.get('city', ''),
            physical_address=sc.get('physical_address', ''),
            next_of_kin_phone=sc.get('next_of_kin_phone', ''),
        )
        plan = None
        _purchase_price = Decimal(str(sp.get('purchase_price') or '0'))
        _deposit_paid = Decimal(str(sp.get('deposit_paid') or '0'))
        _deposit_deductions_total = Decimal(str(sp.get('deposit_deductions_total') or '0'))
        _deposit_deductions = [
            {'label': d.get('label', ''), 'amount': Decimal(str(d.get('amount') or '0'))}
            for d in (sp.get('deposit_deductions') or [])
        ]
        _payment_type = sp.get('payment_type', 'installment')
        _balance = Decimal(str(sp.get('balance') or '0'))
        _installment_months = sp.get('installment_months')
        _purchase_date_str = sp.get('purchase_date', '')
        try:
            _purchase_date = _snap_dt.strptime(_purchase_date_str, '%Y-%m-%d').date() if _purchase_date_str else None
        except Exception:
            _purchase_date = None
        _other_payment_details = sp.get('other_payment_details', '')
        # Build flex schedule from snapshot (for flexible payment type)
        _snap_flex_raw = sp.get('flex_installments', [])
        _snap_flex_schedules = []
        for _fi in _snap_flex_raw:
            _fi_due_str = _fi.get('due_date', '')
            try:
                _fi_due = _snap_dt.strptime(_fi_due_str, '%Y-%m-%d').date() if _fi_due_str else None
            except Exception:
                _fi_due = None
            _snap_flex_schedules.append(SimpleNamespace(
                due_date=_fi_due,
                amount_due=Decimal(str(_fi.get('amount') or '0')),
            ))
        # Build insurance from snapshot
        si = snapshot.get('insurance')
        if si:
            _si_scheds_raw = si.get('schedules', [])
            _si_scheds = []
            for _s in _si_scheds_raw:
                _due_str = _s.get('due_date', '')
                try:
                    _due = _snap_dt.strptime(_due_str, '%Y-%m-%d').date() if _due_str else None
                except Exception:
                    _due = None
                _si_scheds.append(SimpleNamespace(
                    installment_number=_s.get('installment_number', 0),
                    due_date=_due,
                    amount_due=Decimal(str(_s.get('amount_due') or '0')),
                    is_paid=_s.get('is_paid', False),
                ))
            insurance_policy = SimpleNamespace(
                selling_price=Decimal(str(si.get('selling_price') or '0')),
                payment_type=si.get('payment_type', 'installment'),
                vehicle_usage=si.get('vehicle_usage', 'private'),
                has_payment_plan=si.get('has_payment_plan', False),
                insurance_installment_months=si.get('insurance_installment_months'),
                insurance_deposit=Decimal(str(si.get('insurance_deposit') or '0')),
                insurance_total_paid=Decimal(str(si.get('insurance_total_paid') or '0')),
                insurance_payment_method=si.get('insurance_payment_method', ''),
                insurance_payment_schedules=SimpleNamespace(order_by=lambda _: _si_scheds),
            )
        else:
            insurance_policy = None
        # Build trackers from snapshot
        trackers = []
        for _t in snapshot.get('trackers', []):
            _mi = _t.get('monthly_installment')
            trackers.append(SimpleNamespace(
                tracker_name=_t.get('tracker_name', ''),
                selling_price=Decimal(str(_t.get('selling_price') or '0')),
                payment_type=_t.get('payment_type', 'installment'),
                has_payment_plan=_t.get('has_payment_plan', False),
                installment_months=_t.get('installment_months'),
                deposit=Decimal(str(_t.get('deposit') or '0')),
                total_paid=Decimal(str(_t.get('total_paid') or '0')),
                installments_json=_t.get('installments_json', '[]'),
                payment_method=_t.get('payment_method', ''),
                monthly_installment=Decimal(str(_mi)) if _mi else None,
                installed_date=None,
            ))
        try:
            agreement_signature = client_vehicle.agreement_signature
        except Exception:
            agreement_signature = None
        selected_months = _installment_months
        is_full_payment = (_payment_type == 'full') or (_balance <= Decimal('0.00'))
    else:
        vehicle = client_vehicle.vehicle
        client = client_vehicle.client
        try:
            plan = client_vehicle.installment_plan
        except Exception:
            plan = None
        try:
            from apps.insurance.models import InsurancePolicy
            insurance_policy = InsurancePolicy.objects.filter(
                vehicle=vehicle,
                client=client,
            ).order_by('-created_at').first()
        except Exception:
            insurance_policy = None
        trackers = list(client_vehicle.trackers.all().order_by('created_at'))
        try:
            agreement_signature = client_vehicle.agreement_signature
        except Exception:
            agreement_signature = None
        _purchase_price = client_vehicle.purchase_price
        _deposit_paid = client_vehicle.deposit_paid
        _deposit_deductions_total = client_vehicle.deposit_deductions_total or Decimal('0.00')
        try:
            _deposit_deductions = [
                {'label': d.get('label', ''), 'amount': Decimal(str(d.get('amount') or '0'))}
                for d in json.loads(client_vehicle.deposit_deductions_json or '[]')
            ]
        except (TypeError, ValueError):
            _deposit_deductions = []
        _payment_type = client_vehicle.payment_type
        _balance = client_vehicle.balance or Decimal('0.00')
        _installment_months = client_vehicle.installment_months
        _purchase_date = client_vehicle.purchase_date
        _other_payment_details = getattr(client_vehicle, 'other_payment_details', '') or ''
        _snap_flex_schedules = []  # not used for live data; plan schedules are read directly
        selected_months = None
        if plan and plan.number_of_installments:
            selected_months = plan.number_of_installments
        elif _installment_months:
            selected_months = _installment_months
        is_full_payment = (_payment_type == 'full') or (_balance <= Decimal('0.00'))

    client_id_display = (client.id_number or '').replace('-', '')

    def _payment_type_label(value):
        return {
            'full': 'Full Payment',
            'installment': 'Installment',
            'flexible': 'Flexible Installments',
            'monthly': 'Monthly',
            'weekly': 'Weekly',
            'deduct_from_deposit': 'Deduct from Deposit',
        }.get(value, value or '')

    def _ordinal(n):
        if 10 <= (n % 100) <= 20:
            suffix = 'TH'
        else:
            suffix = {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')
        return f'{n}{suffix}'

    def _signature_flowable(signature_data, width=5.5 * cm, height=1.5 * cm):
        if not signature_data:
            return Paragraph('___________________________', normal_small)
        try:
            encoded = signature_data.split(',', 1)[1] if ',' in signature_data else signature_data
            image_bytes = BytesIO(base64.b64decode(encoded))
            image = Image(image_bytes, width=width, height=height)
            image.hAlign = 'LEFT'
            return image
        except Exception:
            return Paragraph('___________________________', normal_small)

    generated_at = timezone.localtime(timezone.now())
    agreement_date = generated_at.strftime("%d-%m-%Y")

    assigned_by_user = client_vehicle.created_by
    if assigned_by_user:
        assigned_by_name = assigned_by_user.get_full_name().strip() or getattr(assigned_by_user, 'username', '') or 'Unknown User'
    else:
        assigned_by_name = 'Unknown User'

    # ============================================================
    # PAGE 1 — SALES AGREEMENT
    # ============================================================

    # ---- HEADER ----
    header_data = [
        [
            Paragraph('<b>SALES AGREEMENT</b>', title_style),
            ''
        ],
        [
            Paragraph('<b>HOZA INVESTMENT K LIMITED</b>', heading_style),
            ''
        ],
        [
            Paragraph('HOTEL Mombasa - Kenya Mombasa - Kenya', normal_small),
            ''
        ],
        [
            Paragraph('P.O BOX 43074-80100 MOMBASA, E-mail: hozainvltd@gmail.com', normal_small),
            ''
        ],
        [
            Paragraph('Mobile: +254700170447/+254784170447', normal_small),
            ''
        ],
    ]
    header_table = Table(header_data, colWidths=[12*cm, 6*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)

    # Company PIN + Agreement Date
    company_data = [
        [
            Paragraph('<b>COMPANY PIN/VAT NO.</b> PO51811452A', normal_small),
            Paragraph(f'<b>AGREEMENT DATE:</b> {agreement_date}', normal_small),
        ],
    ]
    company_table = Table(company_data, colWidths=[10*cm, 8*cm])
    company_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(company_table)
    elements.append(Spacer(1, 0.3*cm))

    # ---- DESCRIPTION OF THE VEHICLE ----
    vehicle_heading = Paragraph('<b>DESCRIPTION OF THE VEHICLE</b>', heading_style)

    vehicle_data = [
        [
            Paragraph(f'<b>VEHICLE MAKE:</b> {vehicle.make or ""}', normal_small),
            Paragraph(f'<b>MODEL:</b> {vehicle.model or ""}', normal_small),
            Paragraph(f'<b>REG NO:</b> {vehicle.registration_number or ""}', normal_small),
        ],
        [
            Paragraph(f'<b>CHASSIS NO:</b> {vehicle.vin or ""}', normal_small),
            Paragraph(f'<b>ENGINE NO:</b> {vehicle.engine_number or ""}', normal_small),
            Paragraph(f'<b>FUEL:</b> {vehicle.fuel_type or ""}', normal_small),
        ],
        [
            Paragraph(f'<b>ENGINE CC:</b> {vehicle.engine_size or ""}', normal_small),
            Paragraph(f'<b>COLOUR:</b> {vehicle.color or ""}', normal_small),
            Paragraph(f'<b>MODEL YEAR:</b> {vehicle.year or ""}', normal_small),
        ],
    ]
    vehicle_table = Table(vehicle_data, colWidths=[6.5*cm, 6.5*cm, 5*cm])
    vehicle_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(KeepTogether([vehicle_heading, vehicle_table]))
    elements.append(Spacer(1, 0.3*cm))

    # ---- CLIENT PERSONAL DETAILS ----
    client_heading = Paragraph('<b>CLIENT PERSONAL DETAILS</b>', heading_style)

    client_data = [
        [
            Paragraph(f'<b>NAME OF THE BUYER:</b> {client.get_full_name()}', normal_small),
            '',
        ],
        [
            Paragraph(f'<b>CELL PHONE:</b> {client.phone_primary or ""}', normal_small),
            Paragraph(f'<b>ID NO:</b> {client_id_display}', normal_small),
        ],
        [
            Paragraph(f'<b>PIN NO:</b> {client.kra_pin or ""}', normal_small),
            Paragraph(f'<b>EMAIL ADDRESS:</b> {client.email or ""}', normal_small),
        ],
        [
            Paragraph(f'<b>P.O BOX:</b> {client.postal_address or ""}  <b>CODE:</b>   <b>TOWN:</b> {client.city or ""}', normal_small),
            Paragraph(f'<b>PHYSICAL ADDRESS:</b> {client.physical_address or ""}', normal_small),
        ],
        [
            Paragraph(f'<b>NEXT OF KIN CELL PHONE NO:</b> {client.next_of_kin_phone or ""}', normal_small),
            '',
        ],
    ]
    client_table = Table(client_data, colWidths=[9.5*cm, 8.5*cm])
    client_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(KeepTogether([client_heading, client_table]))
    elements.append(Spacer(1, 0.3*cm))

    # ---- PRICING DETAILS ----
    client_final_price = _purchase_price or Decimal('0.00')
    deposit_paid = _deposit_paid or Decimal('0.00')
    # Always derive balance from price minus deposit so the PDF is correct
    # even when the stored balance field is stale.
    balance_amount = max(Decimal('0.00'), client_final_price - deposit_paid)

    price_data = [
        [
            Paragraph(f'<b>PRICE (KES):</b> {float(client_final_price):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_amount_to_words(client_final_price)}', normal_small),
        ],
    ]

    deposit_deductions_total = _deposit_deductions_total or Decimal('0.00')
    gross_deposit_received = deposit_paid + deposit_deductions_total

    if deposit_deductions_total > Decimal('0.00'):
        gross_label = 'AMOUNT RECEIVED IN FULL' if is_full_payment else 'AMOUNT RECEIVED (DEPOSIT)'
        price_data.append([
            Paragraph(f'<b>{gross_label}:</b> KES {float(gross_deposit_received):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_amount_to_words(gross_deposit_received)}', normal_small),
        ])
        for item in _deposit_deductions:
            price_data.append([
                Paragraph(f'<b>LESS — {item["label"]} (Deducted from Deposit):</b> KES {float(item["amount"]):,.2f}', normal_small),
                '',
            ])
        net_label = 'NET AMOUNT CREDITED TO VEHICLE'
        price_data.append([
            Paragraph(f'<b>{net_label}:</b> KES {float(deposit_paid):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_amount_to_words(deposit_paid)}', normal_small),
        ])
    elif deposit_paid > Decimal('0.00'):
        if is_full_payment:
            paid_label = 'AMOUNT PAID IN FULL'
        else:
            paid_label = 'AMOUNT PAID (DEPOSIT)'
        price_data.append([
            Paragraph(f'<b>{paid_label}:</b> KES {float(deposit_paid):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_amount_to_words(deposit_paid)}', normal_small),
        ])

    if not is_full_payment and balance_amount > Decimal('0.00'):
        price_data.append([
            Paragraph(f'<b>BALANCE:</b> KES {float(balance_amount):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_amount_to_words(balance_amount)}', normal_small),
        ])

    price_table = Table(price_data, colWidths=[9.5*cm, 8.5*cm])
    price_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(price_table)
    elements.append(Spacer(1, 0.2*cm))

    # "TO BE PAID IN X MONTHS" line (only for non-full payment plans)
    if not is_full_payment:
        months_text = str(selected_months) if selected_months else ''
        elements.append(Paragraph(
            f'<b>TO BE PAID IN</b> {months_text} <b>MONTH(S) [AS STIPULATED IN THE AGREED TERMS AND CONDITION]</b>',
            normal_small
        ))
        elements.append(Spacer(1, 0.2*cm))

    # Extra Terms and Conditions note (page 1)
    elements.append(Paragraph('<b>EXTRA TERMS AND CONDITIONS - NOTE:</b> _' + '_' * 80, normal_small))
    elements.append(Paragraph('_' * 110, normal_small))
    elements.append(Spacer(1, 0.3*cm))

    # Page 1 — Buyer / Seller signatures
    sig1_data = [
        [
            Paragraph("<b>Buyer's Signature</b>", normal_small),
            Paragraph('<b>Seller\'s Signature</b>', normal_small),
        ],
        [
            _signature_flowable(getattr(agreement_signature, 'signature_data', ''), width=8*cm, height=2*cm),
            _signature_flowable(getattr(agreement_signature, 'seller_signature_data', ''), width=8*cm, height=2*cm),
        ],
        [
            Paragraph(f'<b>{client.get_full_name()}</b>', normal_small),
            Paragraph(getattr(agreement_signature, 'seller_name', '') or 'For HOZA INVESTMENT (K) LTD', normal_small),
        ],
    ]
    sig1_table = Table(sig1_data, colWidths=[9.5*cm, 8.5*cm])
    sig1_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor('#d1d5db')),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(KeepTogether([sig1_table]))

    # ============================================================
    # PAGE 2 — INSURANCE & TRACKER DETAILS
    # ============================================================
    elements.append(PageBreak())

    # Page 2 mini-header
    elements.append(Paragraph('<b>HOZA INVESTMENT (K) LTD — INSURANCE &amp; TRACKER DETAILS</b>', title_style))
    elements.append(Paragraph(
        f'<b>Vehicle:</b> {vehicle.make or ""} {vehicle.model or ""}  '
        f'<b>Reg:</b> {vehicle.registration_number or ""}  '
        f'<b>Client:</b> {client.get_full_name()}',
        normal_small
    ))
    elements.append(Spacer(1, 0.3*cm))

    # ---- INSURANCE & TRACKER ADD-ONS ----
    import json as _json_pdf
    from datetime import datetime as _dt_pdf

    _PAYMENT_METHOD_LABELS = {
        'cash': 'Cash', 'mpesa': 'M-Pesa', 'bank_transfer': 'Bank Transfer',
        'cheque': 'Cheque', 'card': 'Credit/Debit Card', 'other': 'Other',
    }

    # Shared table styles
    def _detail_table_style():
        return TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f4ff')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a6e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('LEADING', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#c7d2e8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f9ff')]),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

    def _schedule_table_style():
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('LEADING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

    # ---- INSURANCE TABLE ----
    if insurance_policy:
        ins_price = insurance_policy.selling_price or Decimal('0.00')
        ins_total_paid = insurance_policy.insurance_total_paid or Decimal('0.00')
        ins_balance = max(Decimal('0.00'), ins_price - ins_total_paid)
        ins_deposit = insurance_policy.insurance_deposit or Decimal('0.00')
        ins_method_label = _PAYMENT_METHOD_LABELS.get(
            insurance_policy.insurance_payment_method or '',
            (insurance_policy.insurance_payment_method or '').replace('_', ' ').title() or '—'
        )

        # Header spans both columns
        ins_detail_rows = [
            [Paragraph('<b>INSURANCE</b>', ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white)), ''],
            ['Price', f'KES {float(ins_price):,.2f}'],
            ['Vehicle Usage', 'Private' if insurance_policy.vehicle_usage == 'private' else 'PSV'],
        ]

        if insurance_policy.payment_type == 'full':
            ins_detail_rows.append(['Status', 'PAID IN FULL'])
        else:
            if ins_deposit > Decimal('0.00'):
                ins_detail_rows.append(['Deposit Paid', f'KES {float(ins_deposit):,.2f}'])
            if ins_total_paid > ins_deposit:
                ins_detail_rows.append(['Total Paid', f'KES {float(ins_total_paid):,.2f}'])
            ins_detail_rows.append(['Balance Remaining', f'KES {float(ins_balance):,.2f}'])
            if insurance_policy.has_payment_plan:
                months = insurance_policy.insurance_installment_months or '—'
                ins_detail_rows.append(['Plan', f'Deposit KES {float(ins_deposit):,.2f} · {months} Month(s)'])

        ins_detail_table = Table(ins_detail_rows, colWidths=[6*cm, 12*cm])
        style = _detail_table_style()
        style.add('SPAN', (0, 0), (1, 0))
        style.add('ALIGN', (0, 0), (1, 0), 'LEFT')
        ins_detail_table.setStyle(style)
        elements.append(ins_detail_table)

        # Insurance payment schedule
        insurance_schedules = list(insurance_policy.insurance_payment_schedules.order_by('installment_number'))
        if insurance_schedules:
            elements.append(Spacer(1, 0.1*cm))
            sched_rows = [['#', 'Due Date', 'Amount (KES)', 'Balance After (KES)']]
            running_balance = ins_price - ins_deposit
            for sch in insurance_schedules:
                due_str = sch.due_date.strftime('%d-%m-%Y') if sch.due_date else '—'
                amt = sch.amount_due or Decimal('0.00')
                running_balance = max(Decimal('0.00'), running_balance - amt)
                status = ' ✓' if sch.is_paid else ''
                sched_rows.append([
                    f'#{sch.installment_number}{status}',
                    due_str,
                    f'{float(amt):,.2f}',
                    f'{float(running_balance):,.2f}',
                ])
            sched_table = Table(sched_rows, colWidths=[1.5*cm, 4*cm, 6.25*cm, 6.25*cm])
            sched_table.setStyle(_schedule_table_style())
            elements.append(sched_table)
    else:
        elements.append(Paragraph('Insurance: Not included in this sale.', normal_small))

    elements.append(Spacer(1, 0.2*cm))

    # ---- TRACKER TABLE(S) ----
    if trackers:
        for idx, tracker in enumerate(trackers, start=1):
            trk_price = tracker.selling_price or Decimal('0.00')
            trk_total_paid = tracker.total_paid or Decimal('0.00')
            trk_balance = max(Decimal('0.00'), trk_price - trk_total_paid)
            trk_deposit = tracker.deposit or Decimal('0.00')
            trk_method_label = _PAYMENT_METHOD_LABELS.get(
                getattr(tracker, 'payment_method', '') or '',
                (getattr(tracker, 'payment_method', '') or '').replace('_', ' ').title() or '—'
            )

            trk_header_text = f'TRACKER {idx}{": " + tracker.tracker_name if tracker.tracker_name else ""}'
            trk_detail_rows = [
                [Paragraph(f'<b>{trk_header_text}</b>', ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white)), ''],
                ['Price', f'KES {float(trk_price):,.2f}'],
            ]

            if tracker.payment_type == 'full' or trk_balance <= Decimal('0.00'):
                trk_detail_rows.append(['Status', 'PAID IN FULL'])
            else:
                if trk_deposit > Decimal('0.00'):
                    trk_detail_rows.append(['Deposit Paid', f'KES {float(trk_deposit):,.2f}'])
                if trk_total_paid > trk_deposit:
                    trk_detail_rows.append(['Total Paid', f'KES {float(trk_total_paid):,.2f}'])
                trk_detail_rows.append(['Balance Remaining', f'KES {float(trk_balance):,.2f}'])
                if tracker.has_payment_plan and tracker.installment_months:
                    trk_detail_rows.append(['Plan', f'{tracker.installment_months} Month(s)'])

            trk_detail_table = Table(trk_detail_rows, colWidths=[6*cm, 12*cm])
            style = _detail_table_style()
            style.add('SPAN', (0, 0), (1, 0))
            style.add('ALIGN', (0, 0), (1, 0), 'LEFT')
            # Use orange accent for tracker header
            style.add('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#92400e'))
            trk_detail_table.setStyle(style)
            elements.append(trk_detail_table)

            # Tracker payment schedule
            raw_json = getattr(tracker, 'installments_json', '[]') or '[]'
            try:
                trk_installments = _json_pdf.loads(raw_json)
            except Exception:
                trk_installments = []

            # Fallback: auto-generate schedule when JSON is empty but a plan exists
            if not trk_installments and tracker.has_payment_plan and tracker.installment_months:
                start_date = (
                    getattr(tracker, 'installed_date', None)
                    or getattr(client_vehicle, 'purchase_date', None)
                    or _dt_pdf.now().date()
                )
                if hasattr(start_date, 'date'):
                    start_date = start_date.date()
                months = tracker.installment_months
                monthly_amount = tracker.monthly_installment or (
                    (trk_price - trk_deposit) / months if months else Decimal('0.00')
                )
                for m in range(1, months + 1):
                    due = start_date + relativedelta(months=m)
                    trk_installments.append({
                        'due_date': due.strftime('%Y-%m-%d'),
                        'amount': str(monthly_amount.quantize(Decimal('0.01'))),
                    })

            if trk_installments:
                elements.append(Spacer(1, 0.1*cm))
                trk_sched_rows = [['#', 'Due Date', 'Amount (KES)', 'Balance After (KES)']]
                running_trk_balance = trk_price - trk_deposit
                for t_idx, entry in enumerate(trk_installments, start=1):
                    due_raw = str(entry.get('due_date', '')).strip()
                    try:
                        due_str = _dt_pdf.strptime(due_raw, '%Y-%m-%d').strftime('%d-%m-%Y')
                    except Exception:
                        due_str = due_raw or '—'
                    amt = Decimal(str(entry.get('amount', '0') or '0'))
                    running_trk_balance = max(Decimal('0.00'), running_trk_balance - amt)
                    trk_sched_rows.append([
                        f'#{t_idx}',
                        due_str,
                        f'{float(amt):,.2f}',
                        f'{float(running_trk_balance):,.2f}',
                    ])
                trk_sched_table = Table(trk_sched_rows, colWidths=[1.5*cm, 4*cm, 6.25*cm, 6.25*cm])
                trk_sched_table.setStyle(_schedule_table_style())
                elements.append(trk_sched_table)

            if idx < len(trackers):
                elements.append(Spacer(1, 0.15*cm))
    else:
        elements.append(Paragraph('Tracker: Not included in this sale.', normal_small))

    elements.append(Spacer(1, 0.3*cm))

    # Page 2 — Buyer / Seller signatures
    sig2_data = [
        [
            Paragraph("<b>Buyer's Signature</b>", normal_small),
            Paragraph('<b>Seller\'s Signature</b>', normal_small),
        ],
        [
            _signature_flowable(getattr(agreement_signature, 'signature_data', ''), width=8*cm, height=2*cm),
            _signature_flowable(getattr(agreement_signature, 'seller_signature_data', ''), width=8*cm, height=2*cm),
        ],
        [
            Paragraph(f'<b>{client.get_full_name()}</b>', normal_small),
            Paragraph(getattr(agreement_signature, 'seller_name', '') or 'For HOZA INVESTMENT (K) LTD', normal_small),
        ],
    ]
    sig2_table = Table(sig2_data, colWidths=[9.5*cm, 8.5*cm])
    sig2_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor('#d1d5db')),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(KeepTogether([sig2_table]))

    elements.append(Spacer(1, 0.2*cm))

    # ============================================================
    # PAGE 3 — PAYMENT SCHEDULE (only for non-full payment)
    # ============================================================
    if not is_full_payment:
        elements.append(PageBreak())

        # Payment schedule page header
        elements.append(Paragraph('<b>HOZA INVESTMENT (K) LTD - MOMBASA KENYA</b>', title_style))
        elements.append(Paragraph('<b>PAYMENT SCHEDULE</b>', heading_style))
        elements.append(Spacer(1, 0.2*cm))

        # Make + Reg on this page
        sched_header_data = [
            [
                Paragraph(f'<b>MAKE:</b> {vehicle.make or ""} {vehicle.model or ""}', normal_small),
                Paragraph(f'<b>REGISTRATION NO:</b> {vehicle.registration_number or ""}', normal_small),
            ],
        ]
        sched_header_table = Table(sched_header_data, colWidths=[9*cm, 9*cm])
        sched_header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(sched_header_table)

        # Balance / months / end date summary
        if plan and plan.end_date:
            end_date_str = plan.end_date.strftime('%d-%m-%Y')
        elif selected_months and _purchase_date:
            end_date_str = (_purchase_date + relativedelta(months=selected_months)).strftime('%d-%m-%Y')
        else:
            end_date_str = ''

        months_str = str(selected_months) if selected_months else '___'
        end_date_text = end_date_str if end_date_str else '___________'
        elements.append(Paragraph(
            f'<b>BALANCE TO PAY:</b> KES {float(balance_amount):,.2f}  '
            f'<b>IN</b> {months_str} <b>MONTHS FROM AGREEMENT DATE UPTO</b> {end_date_text}',
            normal_small
        ))
        elements.append(Spacer(1, 0.15*cm))
        other_payment_details = _other_payment_details
        if other_payment_details:
            payment_details_text = other_payment_details.strip()
        else:
            payment_details_text = '_' * 70
        elements.append(Paragraph(f'<b>OTHER PAYMENT DETAILS:</b> {payment_details_text}', normal_small))
        elements.append(Spacer(1, 0.2*cm))

        # Installment table
        if plan:
            schedules = list(plan.payment_schedules.all().order_by('installment_number'))
        elif _snap_flex_schedules:
            schedules = _snap_flex_schedules
        else:
            schedules = []

        schedule_count = selected_months or (len(schedules) if schedules else 15)
        if schedule_count < 1:
            schedule_count = 1

        # Build rows: two installments side-by-side per row
        sched_table_data = [
            [
                Paragraph('<b>DATE</b>', normal_small),
                Paragraph('<b>AMOUNT</b>', normal_small),
                Paragraph('', normal_small),
                Paragraph('<b>DATE</b>', normal_small),
                Paragraph('<b>AMOUNT</b>', normal_small),
            ]
        ]

        for i in range(0, schedule_count, 2):
            installment_left = i + 1
            label_left = f'<b>{_ordinal(installment_left)} INSTALMENT</b>'
            if i < len(schedules):
                s = schedules[i]
                date_left = s.due_date.strftime('%d-%m-%Y') if s.due_date else ''
                amt_left = f'KES {float(s.amount_due):,.2f}'
            else:
                date_left = ''
                amt_left = ''

            if i + 1 < schedule_count:
                installment_right = i + 2
                label_right = f'<b>{_ordinal(installment_right)} INSTALMENT</b>'
                if i + 1 < len(schedules):
                    s2 = schedules[i + 1]
                    date_right = s2.due_date.strftime('%d-%m-%Y') if s2.due_date else ''
                    amt_right = f'KES {float(s2.amount_due):,.2f}'
                else:
                    date_right = ''
                    amt_right = ''
            else:
                label_right = ''
                date_right = ''
                amt_right = ''

            sched_table_data.append([
                Paragraph(f'{label_left}  {date_left}', normal_small),
                Paragraph(amt_left, normal_small),
                Paragraph('', normal_small),
                Paragraph(f'{label_right}  {date_right}', normal_small),
                Paragraph(amt_right, normal_small),
            ])

        sched_table = Table(sched_table_data, colWidths=[5.5*cm, 2.8*cm, 0.4*cm, 5.5*cm, 3.8*cm])
        sched_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (1, -1), 0.5, colors.grey),
            ('GRID', (3, 0), (4, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ]))
        elements.append(sched_table)
        elements.append(Spacer(1, 0.4*cm))

        # Payment schedule page signatures
        sched_sig_data = [
            [
                Paragraph("<b>Customer's Signature</b>", normal_small),
                Paragraph('<b>Seller\'s Signature</b>', normal_small),
            ],
            [
                _signature_flowable(getattr(agreement_signature, 'signature_data', '')),
                _signature_flowable(getattr(agreement_signature, 'seller_signature_data', '')),
            ],
            [
                Paragraph(f'{client.get_full_name()}', normal_small),
                Paragraph(getattr(agreement_signature, 'seller_name', '') or 'For HOZA INVESTMENT (K) LTD', normal_small),
            ],
        ]
        sched_sig_table = Table(sched_sig_data, colWidths=[9*cm, 9*cm])
        sched_sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(KeepTogether([sched_sig_table]))

    # ============================================================
    # PAGE 4 — TERMS AND CONDITIONS
    # ============================================================
    elements.append(PageBreak())
    elements.append(Paragraph('<b>HOZA INVESTMENT (K) LTD - MOMBASA KENYA</b>', title_style))
    elements.append(Paragraph('<b>TERMS AND CONDITIONS</b>', heading_style))
    elements.append(Paragraph(
        '<b>IT IS FURTHER AGREED BETWEEN THE PURCHASER &amp; THE VENDOR AS FOLLOWS:-</b>',
        normal_small
    ))
    elements.append(Spacer(1, 0.2*cm))

    english_terms = [
        "1. That the purchaser shall take possession of the motor vehicle immediately upon signing this agreement",
        "2. The motor vehicle sold on 'AS IT IS' and where it is basis and the purchase has taken possession upon being satisfied that same is in proper and sound mechanical, type and body condition",
        "3. This is used vehicle the vendor does not give the purchaser any guarantee or warranty whatsoever as to the worthiness of the motor vehicle and no CLAIM on this account shall be entertained",
        "4. That the COMMITMENT paid herein by the purchaser shall not be refundable in full amount. The fee shall attract a penalty of 60% upon refunding the amount. The minimum commitment fee therefore shall be Kshs.50,000",
        "5. The vendor shall be at liberty to repossess the motor vehicle without any further notice in the event the purchaser defaults in paying any of the remaining balance as agreed and in such a case the purchaser shall meet all the repossess and incidental charges and further, the buyer shall pay the seller a further sum equivalent to 20% MONTHLY of the remain balance as penalty for the default.",
        "6. THAT on repossession of the vehicle the total outstanding balance shall fail due and owing the same shall have to be paid in full within 15 days from the date of such repossession FAILURE to which the vendor shall have the right to sell the motor vehicle to recover the outstanding balance.",
        "7. The purchaser shall not sell the vehicle to a third party or remove it out of Kenya before paying the vendor in full and or change the road license(s) or route without permission and prior notification of the vendor.",
        "8. THAT upon taking possession of the motor vehicle the purchaser shall take an insurance cover as well as the CAR TRACK GADGET if required in case of settling remaining amount of the total price of the car as agreed and this shall be fully facilitated by HOZA Investment (K) Limited via its company's broker and the purchaser should solemnly settle agreeable insurance fee and car track fee. Furthermore, should the motor vehicle be involved in an accident or stolen it shall be the sole responsibility of the purchaser notwithstanding the fact that motor vehicle has not been formally transferred into its/his/her name.",
        "9. THAT the purchaser after acquiring the vehicle has no authority whatsoever to dismantle tracker gadget or any serious mechanical or electric modification without the consent of the vendor.",
        "10. In case the purchaser make any cheques in favour of the vendor for purchase price or any part thereof, the purchaser hereby expressly warrants that there will be sufficient fund on his/her/its account when the said cheque [s] is presented for payment and that in the case of the dishonor of the cheque[s] then the purchaser hereby undertakes liability on the said cheque [s] both in the civil and criminal liability.",
        "11. Upon completion of the purchase price the purchaser is required to pay a transfer fee, and in the case of commercial vehicle pay inspection fee, booking fee, advance tax fee among other fees that are mandatory. Therefore he/she/its should issue pin/ID copies or certificates of registration & required documents for transfer of the log book before it is issued by the vendor to the purchaser.",
    ]

    swahili_terms = [
        "1. Mnunuzi atamiliki gari pindi atakapo tia sahihi kwenye karatasi ya makubaliano",
        "2. Mteja anakubali kununua gari kwa njia ya 'JINSI ILIVYO' na anaridhika kununua kwamba amekubali jinsi ilivyo hali ya kiufundi na muundo",
        "3. Gari hii imetumika na mnunuzi hapewi udhamini wowote wa gari na hakuna lawama yeyote inakubaliwa baada ya kununua gari",
        "4. Pesa iliyolipwa na mnunuzi kama rubuni hairudishwi kwa njia yeyote ila itapunguzwa kwa asili mia sitini [60%] kisha iliyosalia apewe mnunuzi baada ya kujieleza kuhusu kuihairisha shughuli ya kununua gari. Malipo ya rubuni itakuwa kiasi cha 50,000 elfu.",
        "5. Muuzaji anaruhusiwa kuchukua tena gari baada ya mnunuzi kushindwa kulipa malipo yaliyosalia hivyo basi mnunuzi atagharamikia gharama zote za kuchukua ile gari kutoka kwake hadi kwa muuzaji. Mnunuzi atakaposhindwa kulipa pesa kwa muda uliowekwa atamlipa muuzaji pesa zaidi kwa asilimia 20% kila MWEZI ya pesa waliokuwa wamekubaliana kama faini kwa kutotimiza mkataba.",
        "6. Baada ya muuzaji kuchukua ile gari, pesa iliyobakia inatakiwa kulipwa kabla ya siku kumi na mitano (15) na isipolipwa katikati ya huo muda muuzaji anaruhusiwa kuuza gari tena ili apate pesa hizo.",
        "7. Mnunuzi haruhusiwi kuuza ile gari kwa mtu mwingine au kuitoa nje ya Kenya kabla hajalipa muuzaji pesa yote au kubadilisha leseni ya barabara bila idhini ya mwenye gari.",
        "8. Baada ya kumiliki gari, mnunuzi atachukua jukumu ya kulipia bima ya gari na itakuwa mpangilio wa Kampuni ya HOZA Investment (K) Limited itakayo muezesha mnunuzi kupata bima ya namna ilivyo jadiliwa kwa kumhusisha kampuni ya udalali inayoshughulikia maswala ya bima na hata pia shughuli ya mtambo wa kitegesho na kuchunguza muenendo ya gari iwapo mnunuzi atabakisha sehemu ya jumla ya bei ya gari kwa njia ya mkopo na gari kwa namna yeyote ipate ajali ama kuibiwa basi ni jukumu la mnunuzi kuijishughulisha bila ya kumhusisha na kumlaumu muuzaji gari kwa njia yoyote ile.",
        "9. Mnunuzi baada ya kununua gari haswa kwa njia ya mkopo, hastahili kwa namna yeyote ile kuharibu ama kutoa mtambo wa kiegesho ama wa kuchunguza muenendo wa gari na kadhalika bila idhini ya muuzaji.",
        "10. Kama mnunuzi atapeana cheki kwa muuzaji, inaamanisha kuwa mnunuzi yuko na uhakika kwamba katika akaunti yake ya benki ina pesa za kutosha na wakati wa kupeleka hiyo cheki kwenye benki, akaunti yake itakua na pesa pia inaamanisha mnunuzi amechukua huo wadhifa kisheria.",
        "11. Baada ya kulipa pesa zote za kununua gari mnunuzi anahitajika kulipa pesa ya kuhamisha usajili wa gari kwa majina yake, anastahili pia kulipia shughuli za kufanyia gari ukaguzi na shughuli zingine zenye umuhimu za kukamilika pia anafaa kupeana nakala ya pin/kitambulisho na kartasi zote zinazohitajika kwa ajili ya kumiliki logbook kwa majina yake.",
    ]

    # Two-column layout: English left, Swahili right. A header row is
    # included (with repeatRows=1) so that if this table is long enough to
    # spill onto another page, the continuation still identifies itself
    # instead of showing bare clause text with no context.
    terms_header_style = ParagraphStyle(
        'TermsHeader', parent=normal_small, textColor=colors.white, fontName='Helvetica-Bold',
    )
    terms_data = [
        [Paragraph('ENGLISH', terms_header_style), Paragraph('KISWAHILI', terms_header_style)],
    ]
    for eng, swa in zip(english_terms, swahili_terms):
        terms_data.append([
            Paragraph(eng, normal_small),
            Paragraph(swa, normal_small),
        ])
    terms_table = Table(terms_data, colWidths=[9.5*cm, 8.5*cm], repeatRows=1)
    terms_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
    ]))
    elements.append(terms_table)
    elements.append(Spacer(1, 0.3*cm))

    # Oath / acknowledgment line
    elements.append(Paragraph(
        f'I <b>{client.get_full_name()}</b> do read these terms and conditions properly and I bind to all terms and agree to follow them to the latter.',
        normal_small
    ))
    elements.append(Spacer(1, 0.4*cm))

    # ── Page 3 full signature block ──────────────────────────────────────────
    # Helper values
    id_no_text = (
        f'<b>ID NO:</b> {client_id_display}'
        if client_id_display
        else '<b>ID NO:</b> ___________________________'
    )
    witness_name_val = getattr(agreement_signature, 'witness_name', '') or '___________________________'
    witness_phone_val = getattr(agreement_signature, 'witness_phone', '') or '___________________________'
    seller_name_val = getattr(agreement_signature, 'seller_name', '') or 'For HOZA INVESTMENT (K) LTD'

    # Row heights: label rows are short, signature rows are taller, name rows medium
    col_l = 9.5 * cm
    col_r = 8.5 * cm
    sig_h = 2.0 * cm   # height hint for signature image rows

    full_sig_data = [
        # ── Buyer block ──────────────────────────────────────────────────────
        [
            Paragraph("<b>Buyer's Signature</b>", normal_small),
            Paragraph(id_no_text, normal_small),
        ],
        [
            _signature_flowable(
                getattr(agreement_signature, 'signature_data', ''),
                width=col_l - 0.4*cm, height=sig_h,
            ),
            Paragraph('', normal_small),
        ],
        [
            Paragraph(f'<b>{client.get_full_name()}</b>', normal_small),
            Paragraph('', normal_small),
        ],
        # ── Divider row ──────────────────────────────────────────────────────
        [
            Paragraph('', normal_small),
            Paragraph('', normal_small),
        ],
        # ── Witness + Seller block ───────────────────────────────────────────
        [
            Paragraph('<b>WITNESS NAME</b>', normal_small),
            Paragraph('<b>MOBILE</b>', normal_small),
        ],
        [
            Paragraph(witness_name_val, normal_small),
            Paragraph(witness_phone_val, normal_small),
        ],
        [
            Paragraph('<b>WITNESS Signature</b>', normal_small),
            Paragraph("<b>SELLER'S SIGNATURE</b>", normal_small),
        ],
        [
            _signature_flowable(
                getattr(agreement_signature, 'witness_signature_data', ''),
                width=col_l - 0.4*cm, height=sig_h,
            ),
            _signature_flowable(
                getattr(agreement_signature, 'seller_signature_data', ''),
                width=col_r - 0.4*cm, height=sig_h,
            ),
        ],
        [
            Paragraph('', normal_small),
            Paragraph(f'<b>{seller_name_val}</b>', normal_small),
        ],
    ]

    row_heights = [
        0.4 * cm,   # labels: buyer / id-no
        sig_h,      # buyer signature image
        0.4 * cm,   # buyer name
        0.25 * cm,  # spacer divider
        0.4 * cm,   # labels: witness / mobile
        0.4 * cm,   # witness name / mobile value
        0.4 * cm,   # labels: witness sig / seller sig
        sig_h,      # sig images
        0.4 * cm,   # seller name
    ]

    full_sig_table = Table(full_sig_data, colWidths=[col_l, col_r], rowHeights=row_heights)
    full_sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        # Light bottom border under buyer block (below buyer name row)
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor('#d1d5db')),
        # Light bottom border under witness name row
        ('LINEBELOW', (0, 5), (-1, 5), 0.5, colors.HexColor('#d1d5db')),
        # Vertical divider between the two columns in sig rows
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    # Kept together with its own heading so that if it doesn't fit in the
    # remaining space on the terms page, it moves as a whole onto a fresh
    # page — with proper page identity — rather than splitting mid-block.
    elements.append(KeepTogether([
        Paragraph('<b>SIGNATURES</b>', heading_style),
        full_sig_table,
    ]))

    # ============================================================
    # PAGE 5 — PAYMENT DETAILS
    # ============================================================
    elements.append(PageBreak())
    elements.append(Paragraph('<b>PAYMENT DETAILS FOR HOZA INVESTMENT K LIMITED</b>', title_style))
    elements.append(Spacer(1, 0.3*cm))

    paybill_heading_style = ParagraphStyle(
        'PaybillHeadingStyle',
        parent=styles['Normal'],
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    paybill_value_style = ParagraphStyle(
        'PaybillValueStyle',
        parent=styles['Normal'],
        fontSize=34,
        leading=38,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    paybill_account_style = ParagraphStyle(
        'PaybillAccountStyle',
        parent=styles['Normal'],
        fontSize=26,
        leading=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    paybill_note_style = ParagraphStyle(
        'PaybillNoteStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph('<b>PAYBILL</b>', paybill_heading_style))
    elements.append(Spacer(1, 0.15*cm))
    elements.append(Paragraph(f'<b>{paybill}</b>', paybill_value_style))
    elements.append(Spacer(1, 0.15*cm))
    elements.append(Paragraph('<b>A/C: REG FOR THE CAR</b>', paybill_account_style))
    elements.append(Spacer(1, 0.25*cm))
    elements.append(Paragraph('<b>NOTE: WE DO NOT ACCEPT THIRD PARTY PAYMENTS.</b>', paybill_note_style))

    elements.append(Spacer(1, 0.8*cm))

    # RECEIVED BY — show client name & signature if the agreement has been signed
    received_by_name = ''
    if agreement_signature:
        received_by_name = getattr(agreement_signature, 'signer_name', '') or client.get_full_name()
    else:
        received_by_name = client.get_full_name()

    received_sig_data = [
        [
            Paragraph('<b>RECEIVED BY:</b>', normal_style),
            Paragraph(f'<b>{received_by_name}</b>', normal_style),
        ],
        [
            Paragraph('<b>SIGNATURE:</b>', normal_style),
            _signature_flowable(
                getattr(agreement_signature, 'signature_data', '') if agreement_signature else '',
                width=6 * cm, height=1.8 * cm,
            ),
        ],
    ]
    received_table = Table(received_sig_data, colWidths=[4 * cm, 13.5 * cm])
    received_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(KeepTogether([received_table]))
    elements.append(Spacer(1, 1.0*cm))
    elements.append(HRFlowable(width='100%', thickness=0.6, color=colors.grey, spaceBefore=4, spaceAfter=4))
    elements.append(Spacer(1, 0.1*cm))
    elements.append(Paragraph(
        (
            f'Assigned By: {assigned_by_name} | '
            f'Agreement Generated: {generated_at.strftime("%d-%m-%Y %I:%M %p")}'
        ),
        ParagraphStyle(
            'AgreementFooterStyle',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
    ))

    # Build PDF — every page gets the company letterhead footer strip.
    doc.build(elements, onFirstPage=draw_letterhead_footer, onLaterPages=draw_letterhead_footer)
    buffer.seek(0)
    return buffer


def _number_to_words(number):
    """
    Convert a number to words for KES amounts, including cents.
    """
    try:
        amount = Decimal(str(number)).quantize(Decimal('0.01'))

        def convert_hundreds(value):
            ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
            teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
            tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

            parts = []
            hundreds = value // 100
            remainder = value % 100

            if hundreds:
                parts.append(f'{ones[hundreds]} Hundred')

            if remainder:
                if remainder < 10:
                    parts.append(ones[remainder])
                elif remainder < 20:
                    parts.append(teens[remainder - 10])
                else:
                    tens_word = tens[remainder // 10]
                    ones_word = ones[remainder % 10]
                    parts.append(f'{tens_word} {ones_word}'.strip())

            return ' '.join(part for part in parts if part).strip()

        def convert_integer(value):
            if value == 0:
                return 'Zero'

            scales = [
                (1_000_000_000, 'Billion'),
                (1_000_000, 'Million'),
                (1_000, 'Thousand'),
                (1, ''),
            ]

            parts = []
            remainder = value
            for divisor, label in scales:
                chunk = remainder // divisor
                remainder %= divisor
                if not chunk:
                    continue
                chunk_words = convert_hundreds(chunk)
                if label:
                    parts.append(f'{chunk_words} {label}')
                else:
                    parts.append(chunk_words)

            return ' '.join(parts).strip()

        whole_amount = int(amount)
        cents = int((amount - Decimal(str(whole_amount))) * 100)

        words = convert_integer(whole_amount)
        if cents:
            words = f'{words} and {convert_integer(cents)} Cents'

        return words
    except Exception:
        return ''


def _amount_to_words(number):
    """Format an amount as words with Kenya Shillings and optional cents."""
    try:
        amount = Decimal(str(number)).quantize(Decimal('0.01'))
        whole_amount = int(amount)
        cents = int((amount - Decimal(str(whole_amount))) * 100)

        if cents:
            return f'{_number_to_words(whole_amount)} Kenya Shillings and {_number_to_words(cents)} Cents Only'
        return f'{_number_to_words(whole_amount)} Kenya Shillings Only'
    except Exception:
        return ''
