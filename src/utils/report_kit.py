"""
Shared building blocks for every business report in the system.

Every report — Financial, Client Ledger, Business Loans, Expenses, Payroll,
Insurance, Broker/Agent ledgers, Main Ledger, Auctions, Documents, Audit — is
expected to render as: filter form -> on-page preview -> PDF / Excel / CSV
export, using these helpers so all exports share one letterhead, one color
palette and one table style rather than each view inventing its own.
"""
import csv
import io

from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape as _landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from utils.letterhead import (
    draw_letterhead, FOOTER_RESERVED_HEIGHT, HEADER_RESERVED_HEIGHT,
)

# ---------------------------------------------------------------------------
# Shared palette — muted slate/navy, deliberately avoids bright gradients
# ---------------------------------------------------------------------------
NAVY = colors.HexColor('#1e293b')
ACCENT = colors.HexColor('#334155')
LIGHT_GREY = colors.HexColor('#f1f5f9')
BORDER_GREY = colors.HexColor('#cbd5e1')
MUTED_TEXT = colors.HexColor('#64748b')

EXCEL_HEADER_FILL = '334155'
EXCEL_HEADER_FONT_COLOR = 'FFFFFF'
EXCEL_ZEBRA_FILL = 'F1F5F9'
EXCEL_BORDER_COLOR = 'CBD5E1'


def fmt_money(amount, currency='KES'):
    amount = amount or 0
    return f"{currency} {amount:,.2f}"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _report_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        'ReportCompanyName', parent=styles['Normal'], fontSize=14,
        fontName='Helvetica-Bold', textColor=NAVY, leading=16,
    ))
    styles.add(ParagraphStyle(
        'ReportCompanyMeta', parent=styles['Normal'], fontSize=8,
        textColor=MUTED_TEXT, leading=11,
    ))
    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'], fontSize=16,
        textColor=NAVY, alignment=TA_CENTER, spaceBefore=6, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'], fontSize=9,
        textColor=MUTED_TEXT, alignment=TA_CENTER, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        'ReportSectionHeading', parent=styles['Heading2'], fontSize=11,
        textColor=NAVY, spaceBefore=12, spaceAfter=6,
    ))
    return styles


def build_pdf_response(filename, title, subtitle=None, meta_lines=None,
                        build_body=None, landscape_mode=False):
    """
    Render a complete letterhead + title + footer PDF and return it as a
    file-download HttpResponse. `build_body(elements, styles)` appends the
    report-specific Flowables (KPI blocks, tables, notes). The company
    letterhead (header band + footer trust strip) is drawn on the canvas by
    utils.letterhead so it's identical across every report and doesn't
    consume space in the flowable body.
    """
    buffer = io.BytesIO()
    pagesize = _landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        topMargin=HEADER_RESERVED_HEIGHT + 0.1 * inch,
        bottomMargin=FOOTER_RESERVED_HEIGHT + 0.1 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = _report_styles()
    elements = []

    elements.append(Paragraph(title.upper(), styles['ReportTitle']))
    sub_bits = [subtitle] if subtitle else []
    sub_bits.append(f"Generated {timezone.now().strftime('%d %B %Y, %H:%M')}")
    elements.append(Paragraph(' &middot; '.join(sub_bits), styles['ReportSubtitle']))

    if meta_lines:
        for line in meta_lines:
            elements.append(Paragraph(line, styles['Normal']))
        elements.append(Spacer(1, 8))

    if build_body:
        build_body(elements, styles)

    doc.build(elements, onFirstPage=draw_letterhead, onLaterPages=draw_letterhead)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def styled_table(data, col_widths=None, align_right_from=None, font_size=8, header=True):
    """A Table flowable using the shared slate header + zebra-striped body."""
    table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    if header:
        style += [
            ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ]
    if align_right_from is not None:
        style.append(('ALIGN', (align_right_from, 0), (-1, -1), 'RIGHT'))
    table.setStyle(TableStyle(style))
    return table


def kpi_table(pairs, col_widths=None):
    """A compact label/value summary block (bold label, right-aligned value)."""
    data = [[label, value] for label, value in pairs]
    table = Table(data, colWidths=col_widths or [2.6 * inch, 2.6 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER_GREY),
    ]))
    return table


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def build_excel_response(filename, sheet_title, headers, rows, currency_cols=None, widths=None):
    """
    A single-sheet workbook with a bold white-on-slate frozen header row,
    zebra striping, right-aligned KES-formatted currency columns, thin
    borders and auto column widths.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    header_font = Font(bold=True, color=EXCEL_HEADER_FONT_COLOR)
    header_fill = PatternFill('solid', fgColor=EXCEL_HEADER_FILL)
    zebra_fill = PatternFill('solid', fgColor=EXCEL_ZEBRA_FILL)
    thin = Side(style='thin', color=EXCEL_BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.append(headers)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    ws.freeze_panes = 'A2'

    currency_cols = currency_cols or set()
    for r_idx, row in enumerate(rows, start=2):
        ws.append(row)
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.border = border
            if r_idx % 2 == 0:
                cell.fill = zebra_fill
            if c_idx in currency_cols:
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right')

    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
    else:
        for i, h in enumerate(headers, start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(12, len(str(h)) + 4)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def build_csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


# ---------------------------------------------------------------------------
# Generic single-table dispatcher — for simple reports that are just one
# headers/rows table, so the view only has to build the data once.
# ---------------------------------------------------------------------------

def export_rows(fmt, filename_base, title, headers, rows, currency_cols=None, subtitle=None):
    """Render `rows` as a PDF, Excel or CSV download depending on `fmt`."""
    currency_cols = currency_cols or set()
    if fmt == 'excel':
        return build_excel_response(f'{filename_base}.xlsx', title, headers, rows, currency_cols=currency_cols)
    if fmt == 'csv':
        return build_csv_response(f'{filename_base}.csv', headers, rows)

    align_right_from = (min(currency_cols) - 1) if currency_cols else None

    def body(elements, styles):
        table_data = [headers] + [[str(c) for c in row] for row in rows]
        elements.append(styled_table(table_data, align_right_from=align_right_from))

    return build_pdf_response(f'{filename_base}.pdf', title, subtitle=subtitle, build_body=body)
