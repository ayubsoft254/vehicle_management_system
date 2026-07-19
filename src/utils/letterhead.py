"""
Shared PDF letterhead for Hoza Investment (K) Limited.

Every generated system document (reports via report_kit.py, the sales
agreement, payment/proforma PDFs) should draw the same header band and
footer strip so they look like they came from one company, not from
whichever view happened to build them. Drawn directly on the canvas via
reportlab's onFirstPage/onLaterPages hooks so it repeats identically on
every page regardless of how that page's own flowable content is laid out.

There is no company logo image file in the repo (checked static/ and
media/), so the letterhead is drawn natively — navy/orange accent bars,
company name + tagline, contact block, and the four trust taglines from
the company letterhead — rather than embedding a raster logo.
"""
from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.units import inch

NAVY = colors.HexColor('#1e293b')
ORANGE = colors.HexColor('#f97316')
MUTED_TEXT = colors.HexColor('#64748b')
BORDER_GREY = colors.HexColor('#cbd5e1')

COMPANY_TAGLINE = 'IMPORTERS & EXPORTERS OF JAPANESE, QUALITY VEHICLES'

FOOTER_TAGLINES = [
    'Quality Vehicles You Can Trust',
    'Reliable Imports, Best Standards',
    'Integrity & Transparency',
    'Driven By Trust, Focused On You',
]

# Reserve this much space at the top/bottom of every page for the letterhead.
# Callers should set topMargin/bottomMargin at least this large so body
# content never overlaps the drawn bands.
HEADER_RESERVED_HEIGHT = 1.05 * inch
FOOTER_RESERVED_HEIGHT = 0.75 * inch


def _corner_wedge(canvas, x0, y0, width, height, flip_y=False):
    """A right-angled orange wedge, used as the diagonal corner accent."""
    canvas.setFillColor(ORANGE)
    p = canvas.beginPath()
    if flip_y:
        p.moveTo(x0, y0 + height)
        p.lineTo(x0 + width, y0 + height)
        p.lineTo(x0 + width, y0)
    else:
        p.moveTo(x0, y0)
        p.lineTo(x0 + width, y0)
        p.lineTo(x0 + width, y0 + height)
    p.close()
    canvas.drawPath(p, stroke=0, fill=1)


def draw_letterhead_header(canvas, doc):
    """Company name, tagline, contact block and navy/orange accent bar."""
    canvas.saveState()
    page_width, page_height = doc.pagesize
    left = 0.75 * inch
    right = page_width - 0.75 * inch
    top = page_height

    # Navy band across the very top edge, with an orange wedge cut into its
    # top-right corner — echoes the printed letterhead's diagonal accent.
    band_height = 0.11 * inch
    canvas.setFillColor(NAVY)
    canvas.rect(0, top - band_height, page_width, band_height, stroke=0, fill=1)
    _corner_wedge(canvas, page_width - 1.6 * inch, top - band_height, 1.6 * inch, band_height, flip_y=False)

    # Company name + tagline (left)
    canvas.setFillColor(NAVY)
    canvas.setFont('Helvetica-Bold', 15)
    canvas.drawString(left, top - 0.42 * inch, settings.COMPANY_NAME.upper())
    canvas.setFillColor(ORANGE)
    canvas.setFont('Helvetica-Bold', 6.5)
    canvas.drawString(left, top - 0.57 * inch, COMPANY_TAGLINE)

    # Contact block (right), one line per non-empty setting
    canvas.setFillColor(NAVY)
    canvas.setFont('Helvetica', 8)
    contact_lines = [b for b in (
        getattr(settings, 'COMPANY_ADDRESS', ''),
        getattr(settings, 'COMPANY_PHONE', ''),
        getattr(settings, 'COMPANY_EMAIL', ''),
    ) if b]
    y = top - 0.30 * inch
    for line in contact_lines:
        canvas.drawRightString(right, y, line)
        y -= 0.15 * inch

    # Orange rule closing off the header band
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.4)
    canvas.line(left, top - HEADER_RESERVED_HEIGHT + 0.12 * inch,
                right, top - HEADER_RESERVED_HEIGHT + 0.12 * inch)
    canvas.restoreState()


def draw_letterhead_footer(canvas, doc):
    """Four trust taglines, page number, and the bottom navy/orange accent bar."""
    canvas.saveState()
    page_width, _page_height = doc.pagesize
    left = 0.75 * inch
    right = page_width - 0.75 * inch

    rule_y = FOOTER_RESERVED_HEIGHT - 0.22 * inch
    canvas.setStrokeColor(BORDER_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(left, rule_y, right, rule_y)

    # Four taglines, evenly spaced, each centered in its own column, with
    # thin dividers between them (mirrors the printed footer strip).
    taglines = FOOTER_TAGLINES
    col_width = (right - left) / len(taglines)
    canvas.setFont('Helvetica-Bold', 6.5)
    canvas.setFillColor(NAVY)
    text_y = rule_y - 0.16 * inch
    for i, text in enumerate(taglines):
        col_left = left + col_width * i
        canvas.drawCentredString(col_left + col_width / 2, text_y, text)
        if i > 0:
            canvas.setStrokeColor(BORDER_GREY)
            canvas.line(col_left, text_y - 0.03 * inch, col_left, text_y + 0.14 * inch)

    # Page number, bottom-left, clear of the corner accent below.
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED_TEXT)
    canvas.drawString(left, 0.12 * inch, f"{settings.COMPANY_NAME} — Page {doc.page}")

    # Navy band across the very bottom edge, with an orange wedge cut into
    # its bottom-right corner.
    band_height = 0.09 * inch
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, page_width, band_height, stroke=0, fill=1)
    _corner_wedge(canvas, page_width - 1.4 * inch, 0, 1.4 * inch, band_height, flip_y=True)
    canvas.restoreState()


def draw_letterhead(canvas, doc):
    """Combined onFirstPage/onLaterPages callback: header + footer."""
    draw_letterhead_header(canvas, doc)
    draw_letterhead_footer(canvas, doc)
