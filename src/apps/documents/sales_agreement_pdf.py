"""
Sales Agreement PDF Generator
Generates a PDF sales agreement with auto-filled vehicle and client information
"""
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from django.utils import timezone


def generate_sales_agreement_pdf(client_vehicle):
    """
    Generate a PDF sales agreement for a vehicle purchase
    
    Args:
        client_vehicle: ClientVehicle instance
        
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title=f"Sales Agreement - {client_vehicle.vehicle.registration_number}"
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
    
    # ============ HEADER ============
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
    
    # Company details and agreement date
    company_data = [
        [
            Paragraph(f'<b>COMPANY PIN/VAT NO.</b> PO51811452A', normal_small),
            Paragraph(f'<b>AGREEMENT DATE:</b> {datetime.now().strftime("%d-%m-%Y")}', normal_small)
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
    
    # ============ VEHICLE DESCRIPTION ============
    elements.append(Paragraph('<b>DESCRIPTION OF THE VEHICLE</b>', heading_style))
    
    vehicle = client_vehicle.vehicle
    vehicle_data = [
        [
            Paragraph(f'<b>VEHICLE MAKE:</b> {vehicle.make or ""}', normal_small),
            Paragraph(f'<b>MODEL:</b> {vehicle.model or ""}', normal_small),
            Paragraph(f'<b>REG NO:</b> {vehicle.registration_number or ""}', normal_small)
        ],
        [
            Paragraph(f'<b>CHASSIS NO:</b> {vehicle.chassis_number or ""}', normal_small),
            Paragraph(f'<b>ENGINE NO:</b> {vehicle.engine_number or ""}', normal_small),
            Paragraph(f'<b>FUEL:</b> {vehicle.fuel_type or ""}', normal_small)
        ],
        [
            Paragraph(f'<b>COLOUR:</b> {vehicle.colour or ""}', normal_small),
            Paragraph(f'<b>YEAR:</b> {vehicle.year_of_manufacture or ""}', normal_small),
            Paragraph(f'<b>ENGINE CC:</b> {vehicle.engine_cc or ""}', normal_small)
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
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # ============ CLIENT PERSONAL DETAILS ============
    elements.append(Paragraph('<b>CLIENT PERSONAL DETAILS</b>', heading_style))
    
    client = client_vehicle.client
    client_data = [
        [
            Paragraph(f'<b>NAME OF THE BUYER:</b> {client.get_full_name()}', normal_small),
            ''
        ],
        [
            Paragraph(f'<b>CELL PHONE:</b> {client.phone_number or ""}', normal_small),
            Paragraph(f'<b>ID NO:</b> {client.id_number or ""}', normal_small)
        ],
        [
            Paragraph(f'<b>PIN NO:</b> {client.pin_number or ""}', normal_small),
            Paragraph(f'<b>EMAIL ADDRESS:</b> {client.email or ""}', normal_small)
        ],
        [
            Paragraph(f'<b>P.O BOX:</b> {client.po_box or ""}', normal_small),
            Paragraph(f'<b>PHYSICAL ADDRESS:</b> {client.physical_address or ""}', normal_small)
        ],
        [
            Paragraph(f'<b>NEXT OF KIN CELL PHONE NO:</b> {client.next_of_kin_phone or ""}', normal_small),
            ''
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
    elements.append(client_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # ============ PRICING DETAILS ============
    price_data = [
        [
            Paragraph(f'<b>SALE PRICE IN KSHS:</b> {float(client_vehicle.purchase_price):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_number_to_words(client_vehicle.purchase_price)}', normal_small)
        ],
        [
            Paragraph(f'<b>RECEIVED AMOUNT PAID:</b> KES {float(client_vehicle.deposit_paid):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_number_to_words(client_vehicle.deposit_paid)}', normal_small)
        ],
        [
            Paragraph(f'<b>REMAINING BALANCE:</b> KES {float(client_vehicle.balance):,.2f}', normal_small),
            Paragraph(f'<b>IN WORDS:</b> {_number_to_words(client_vehicle.balance)}', normal_small)
        ],
    ]
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
    elements.append(Spacer(1, 0.3*cm))
    
    # ============ PAYMENT SCHEDULE ============
    try:
        plan = client_vehicle.installment_plan
        elements.append(Paragraph('<b>PAYMENT SCHEDULE</b>', heading_style))
        
        schedules = plan.payment_schedules.all().order_by('installment_number')[:15]
        
        if schedules.exists():
            schedule_data = [['INSTALLMENT', 'DUE DATE', 'AMOUNT', '', 'INSTALLMENT', 'DUE DATE', 'AMOUNT']]
            
            # Format data in 2 columns
            schedule_list = list(schedules)
            for i in range(0, len(schedule_list), 2):
                row = []
                # First installment
                s1 = schedule_list[i]
                row.append(Paragraph(f'<b>{s1.installment_number}</b>', normal_small))
                row.append(Paragraph(s1.due_date.strftime('%d-%m-%Y') if s1.due_date else '', normal_small))
                row.append(Paragraph(f'KES {float(s1.amount_due):,.2f}', normal_small))
                row.append(Paragraph('', normal_small))
                
                # Second installment (if exists)
                if i + 1 < len(schedule_list):
                    s2 = schedule_list[i + 1]
                    row.append(Paragraph(f'<b>{s2.installment_number}</b>', normal_small))
                    row.append(Paragraph(s2.due_date.strftime('%d-%m-%Y') if s2.due_date else '', normal_small))
                    row.append(Paragraph(f'KES {float(s2.amount_due):,.2f}', normal_small))
                else:
                    row.extend([Paragraph('', normal_small), Paragraph('', normal_small), Paragraph('', normal_small)])
                
                schedule_data.append(row)
            
            schedule_table = Table(schedule_data, colWidths=[1.8*cm, 2.2*cm, 1.8*cm, 0.5*cm, 1.8*cm, 2.2*cm, 1.8*cm])
            schedule_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ]))
            elements.append(schedule_table)
            elements.append(Spacer(1, 0.3*cm))
    except:
        pass
    
    # ============ TERMS AND CONDITIONS ============
    elements.append(PageBreak())
    elements.append(Paragraph('<b>TERMS AND CONDITIONS</b>', heading_style))
    
    terms = [
        "1. That the purchaser shall take possession of the motor vehicle immediately upon signing this agreement",
        "2. The motor vehicle sold on 'AS IT IS' and where it is basis and the purchase has taken possession upon being satisfied that same is in proper and sound mechanical, type and body condition",
        "3. This is used vehicle the vendor does not give the purchaser any guarantee or warranty whatsoever as to the worthiness of the motor vehicle and no CLAIM on this account shall be entertained",
        "4. That the COMMITMENT paid herein by the purchaser shall not be refundable in full amount. The fee shall attract a penalty of 60% upon refunding the amount. The minimum commitment fee therefore shall be Kshs.50,000",
        "5. The vendor shall be at liberty to repossess the motor vehicle without any further notice in the event the purchaser defaults in paying any of the remaining balance as agreed and in such a case the purchaser shall meet all the repossess and incidental charges and further, the buyer shall pay the seller a further sum equivalent to 20% MONTHLY of the remain balance as penalty for the default.",
        "6. THAT on repossession of the vehicle the total outstanding balance shall fail due and owing the same shall have to be paid in full within 15 days from the date of such repossession FAILURE to which the vendor shall have the right to sell the motor vehicle to recover the outstanding balance.",
        "7. The purchaser shall not sell the vehicle to a third party or remove it out of Kenya before paying the vendor in full and or change the road license(s) or route without permission and prior notification of the vendor.",
        "8. THAT upon taking possession of the motor vehicle the purchaser shall take an insurance cover as well as the CAR TRACK GADGET if required in case of settling remaining amount of the total price of the car as agreed and this shall be fully facilitated by HOZA Investment (K) Limited via its company's brokerand the purchaser should solemnly settle agreeable insurance fee and car track fee. Furthermore, should the motor vehicle be involved in an accident or stolen it shall be the sole responsibility of the purchaser notwithstanding the fact that motor vehicle has not been formally transferred into its/his/her name.",
        "9. THAT the purchaser after acquiring the vehicle has no authority whatsoever to dismantle tracker gadget or any serious mechanical or electric modification without the consent of the vendor",
        "10. In case the purchaser make any cheques in favour of the vendor for purchase price or any part thereof, the purchaser hereby expressly warrants that there will be sufficient fund on his/her /its account when the said cheque [s] is presented for payment and that in the case of the dishonor of the cheque[s] then the purchaser hereby undertakes liability on the said cheque [s] both in the civil and criminal liability.",
        "11. Upon completion of the purchase price the purchaser is required to pay a transfer fee, and in the case of commercial vehicle pay inspection fee, booking fee, advance tax fee among other fees that are mandatory. Therefore he/she/its should issue pin/ID copies or certificates of registration & required documents for transfer of the log book before it is issued by the vendor to the purchaser.",
    ]
    
    for term in terms:
        elements.append(Paragraph(term, normal_small))
        elements.append(Spacer(1, 0.15*cm))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # ============ SIGNATURES ============
    signature_data = [
        [
            Paragraph('<b>Buyer\'s Signature</b>', normal_small),
            Paragraph('<b>Seller\'s Signature</b>', normal_small),
        ],
        [
            Paragraph('___________________________', normal_small),
            Paragraph('___________________________', normal_small),
        ],
        [
            Paragraph(f'Name: {client.get_full_name()}', normal_small),
            Paragraph('For HOZA INVESTMENT (K) LTD', normal_small),
        ],
        [
            Paragraph(f'Date: _____________________', normal_small),
            Paragraph('Date: _____________________', normal_small),
        ],
    ]
    
    signature_table = Table(signature_data, colWidths=[9*cm, 9*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(signature_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def _number_to_words(number):
    """
    Convert a number to words (simplified version for KES)
    """
    try:
        num = int(float(number))
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
        
        if num == 0:
            return 'Zero'
        
        if num < 10:
            return ones[num]
        elif num < 20:
            return teens[num - 10]
        elif num < 100:
            return tens[num // 10] + (' ' + ones[num % 10] if num % 10 else '')
        elif num < 1000:
            return ones[num // 100] + ' Hundred' + (' ' + _number_to_words(num % 100) if num % 100 else '')
        elif num < 1000000:
            return _number_to_words(num // 1000) + ' Thousand' + (' ' + _number_to_words(num % 1000) if num % 1000 else '')
        else:
            return str(num)
    except:
        return ''
