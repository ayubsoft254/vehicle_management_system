"""
Shared PDF letterhead for the company.

Every generated system document (reports via report_kit.py, the sales
agreement, payment/proforma PDFs) draws the same header band and footer
strip so they look like they came from one company, not from whichever
view happened to build them. Callers pass draw_letterhead (header + footer)
or draw_letterhead_footer (footer only) as reportlab's
onFirstPage/onLaterPages hooks and reserve HEADER_RESERVED_HEIGHT /
FOOTER_RESERVED_HEIGHT as page margins.

What gets drawn is chosen by the company admin at Settings → Company &
Branding → Documents (CompanyProfile.letterhead_mode):

  generated      built from the logo, company details and theme colours —
                 needs no artwork at all.
  header_footer  two uploaded images, scaled to the page width and fitted
                 inside the reserved header/footer bands.
  full_page      one uploaded image stretched over the whole page (header,
                 watermark and footer together). This is how the original
                 Hoza letterhead works; the footer band for footer-only
                 documents is cropped from the bottom
                 FULL_PAGE_FOOTER_FRACTION of the image.
"""
from functools import lru_cache
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

MUTED_TEXT = colors.HexColor('#64748b')

# Bottom fraction of a full-page letterhead image occupied by its footer
# band — measured on the Hoza artwork (rule + trust badges from y=2065 of
# 2200px), used to crop the footer for footer-only documents.
FULL_PAGE_FOOTER_FRACTION = 135 / 2200

# Reserve this much space at the top/bottom of every page for the letterhead.
# Callers should set topMargin/bottomMargin at least this large (they add a
# further +0.1in buffer on top) so body content never overlaps the artwork.
# Uploaded header/footer images are scaled to fit inside these bands.
HEADER_RESERVED_HEIGHT = 1.8 * inch
FOOTER_RESERVED_HEIGHT = 0.75 * inch


def _company():
    from apps.company.services import get_company
    return get_company()


def _read_field_bytes(field_file):
    if not field_file:
        return None
    try:
        field_file.open('rb')
        try:
            return field_file.read()
        finally:
            field_file.close()
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=64)
def _assets(schema, profile_pk, version):
    """Decoded letterhead images for one profile version. Keyed by version
    so a Settings save is picked up on the next document without a restart."""
    from PIL import Image as PILImage

    profile = _company()
    mode = profile.letterhead_mode
    assets = {'mode': mode}

    def load(field):
        data = _read_field_bytes(field)
        if not data:
            return None
        image = PILImage.open(BytesIO(data))
        image.load()
        return image

    def reader(image):
        buf = BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)
        return ImageReader(buf), image.size

    if mode == 'full_page':
        full = load(profile.letterhead_full_page)
        if full is None:
            assets['mode'] = 'generated'
        else:
            # Embed the original file (usually a JPEG) rather than a PNG
            # re-encode, which would bloat every PDF by megabytes.
            raw = _read_field_bytes(profile.letterhead_full_page)
            assets['full'] = (ImageReader(BytesIO(raw)), full.size)
            width, height = full.size
            top = int(height * (1 - FULL_PAGE_FOOTER_FRACTION))
            assets['footer'] = reader(full.crop((0, top, width, height)))
    elif mode == 'header_footer':
        header = load(profile.letterhead_header)
        footer = load(profile.letterhead_footer)
        if header is None and footer is None:
            assets['mode'] = 'generated'
        if header is not None:
            assets['header'] = reader(header)
        if footer is not None:
            assets['footer'] = reader(footer)

    logo = load(profile.logo)
    if logo is not None:
        assets['logo'] = reader(logo.convert('RGBA'))
    return assets


def _current_assets():
    from utils.tenancy import current_schema
    profile = _company()
    return profile, _assets(current_schema(), profile.pk, profile.version)


def _draw_band(canvas, page_width, image, y, max_height, anchor_top):
    """Draw an image across the page width, shrinking (and centring) it if
    its natural height at full width would overflow max_height."""
    reader, (img_w, img_h) = image
    width = page_width
    height = width * img_h / img_w
    if height > max_height:
        height = max_height
        width = height * img_w / img_h
    x = (page_width - width) / 2
    draw_y = y - height if anchor_top else y
    canvas.drawImage(reader, x, draw_y, width=width, height=height,
                     preserveAspectRatio=False, mask='auto')
    return height


def _draw_page_number(canvas, doc, band_top, name):
    """Drawn just above the footer band — artwork footers often run to the
    bottom page edge, so there's no clear space within the band itself."""
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED_TEXT)
    canvas.drawString(0.75 * inch, band_top + 3, f"{name} — Page {doc.page}")


def _theme_colors(profile):
    from utils.theme import palette
    primary = palette(profile.primary_color)
    accent = palette(profile.accent_color)
    return colors.HexColor(primary[700]), colors.HexColor(accent[500])


def _draw_generated_header(canvas, profile, assets, page_width, page_height):
    primary, accent = _theme_colors(profile)
    margin = 0.6 * inch
    top = page_height - 0.4 * inch
    text_x = margin

    logo = assets.get('logo')
    if logo:
        reader, (w, h) = logo
        logo_h = 0.95 * inch
        logo_w = min(logo_h * w / h, 2.2 * inch)
        logo_h = logo_w * h / w
        canvas.drawImage(reader, margin, top - logo_h, width=logo_w, height=logo_h, mask='auto')
        text_x = margin + logo_w + 0.25 * inch

    canvas.setFillColor(primary)
    canvas.setFont('Helvetica-Bold', 15)
    canvas.drawString(text_x, top - 0.22 * inch, profile.legal_name or '')

    canvas.setFillColor(colors.HexColor('#334155'))
    canvas.setFont('Helvetica', 8)
    lines = [
        ' · '.join(filter(None, [profile.postal_address, profile.physical_address])),
        ' · '.join(filter(None, [
            f'Tel: {profile.phone}' if profile.phone else '',
            profile.email,
            profile.website_display,
        ])),
        f'{profile.country_preset["tax_id_label"]}: {profile.tax_pin}' if profile.tax_pin else '',
    ]
    y = top - 0.45 * inch
    for line in filter(None, lines):
        canvas.drawString(text_x, y, line)
        y -= 0.16 * inch

    rule_y = page_height - HEADER_RESERVED_HEIGHT + 0.25 * inch
    canvas.setStrokeColor(primary)
    canvas.setLineWidth(2)
    canvas.line(margin, rule_y, page_width - margin, rule_y)
    canvas.setStrokeColor(accent)
    canvas.setLineWidth(1)
    canvas.line(margin, rule_y - 3, page_width - margin, rule_y - 3)


def _draw_generated_footer(canvas, profile, page_width):
    """Returns the top of the drawn footer band."""
    primary, accent = _theme_colors(profile)
    margin = 0.6 * inch
    rule_y = 0.5 * inch
    canvas.setStrokeColor(accent)
    canvas.setLineWidth(1)
    canvas.line(margin, rule_y + 3, page_width - margin, rule_y + 3)
    canvas.setStrokeColor(primary)
    canvas.setLineWidth(2)
    canvas.line(margin, rule_y, page_width - margin, rule_y)
    canvas.setFillColor(MUTED_TEXT)
    canvas.setFont('Helvetica', 7)
    text = ' · '.join(filter(None, [profile.legal_name, profile.website_display, profile.email, profile.primary_phone]))
    canvas.drawCentredString(page_width / 2, rule_y - 0.18 * inch, text)
    return rule_y + 0.1 * inch


def _draw_footer(canvas, profile, assets, page_width):
    footer = assets.get('footer')
    if assets['mode'] in ('full_page', 'header_footer') and footer:
        return _draw_band(canvas, page_width, footer, 0, FOOTER_RESERVED_HEIGHT, anchor_top=False)
    if assets['mode'] == 'header_footer':
        return 0.3 * inch  # header-only upload: no footer artwork
    return _draw_generated_footer(canvas, profile, page_width)


def draw_letterhead(canvas, doc):
    """Combined onFirstPage/onLaterPages callback: header and footer, then
    the page number."""
    profile, assets = _current_assets()
    canvas.saveState()
    page_width, page_height = doc.pagesize

    if assets['mode'] == 'full_page':
        reader, _size = assets['full']
        canvas.drawImage(reader, 0, 0, width=page_width, height=page_height,
                         preserveAspectRatio=False, mask='auto')
        band_top = page_height * FULL_PAGE_FOOTER_FRACTION
    else:
        if assets['mode'] == 'header_footer' and assets.get('header'):
            _draw_band(canvas, page_width, assets['header'], page_height,
                       HEADER_RESERVED_HEIGHT, anchor_top=True)
        elif assets['mode'] == 'generated':
            _draw_generated_header(canvas, profile, assets, page_width, page_height)
        band_top = _draw_footer(canvas, profile, assets, page_width)

    _draw_page_number(canvas, doc, band_top, profile.legal_name)
    canvas.restoreState()


def draw_letterhead_footer(canvas, doc):
    """Footer-only callback for documents that already build their own
    per-page company-identity header as flowables."""
    profile, assets = _current_assets()
    canvas.saveState()
    page_width, _page_height = doc.pagesize
    band_top = _draw_footer(canvas, profile, assets, page_width)
    _draw_page_number(canvas, doc, band_top, profile.legal_name)
    canvas.restoreState()
