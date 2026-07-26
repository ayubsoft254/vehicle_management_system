"""
Shared PDF letterhead for Hoza Investment (K) Limited.

Every generated system document (reports via report_kit.py, the sales
agreement, payment/proforma PDFs) draws the same header band and footer
strip so they look like they came from one company, not from whichever
view happened to build them.

The letterhead is the company's actual letterhead artwork
(`static/img/letterhead.jpg`, a single full-page image: header band,
watermark car graphic, and footer band all in one) — not hand-drawn
shapes. It's embedded directly via reportlab's onFirstPage/onLaterPages
canvas hooks so it repeats identically on every page.

The source image is a 1700x2200px raster rendered at 200dpi from the
company's letterhead PDF (`static/HOZA LETTER HEAD.1.pdf`, a US-Letter
page — the slight aspect difference vs A4 is absorbed by the full-page
stretch). Measured landmarks used below:
  - header content (logo block + contact rows + navy rule) ends at
    roughly y=335px from the top.
  - footer content (navy/orange rule + trust-badge icon row) starts at
    roughly y=2077px, i.e. ~123px from the bottom.
"""
import os
from functools import lru_cache
from io import BytesIO

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

MUTED_TEXT = colors.HexColor('#64748b')

LETTERHEAD_IMAGE_PATH = os.path.join(settings.BASE_DIR, 'static', 'img', 'letterhead.jpg')

# Fraction of the source image's height occupied by the footer band
# (measured from the top of the orange/navy rule down to the bottom edge).
_FOOTER_CROP_TOP_FRAC = 2065 / 2200

# Reserve this much space at the top/bottom of every page for the letterhead.
# Callers should set topMargin/bottomMargin at least this large (they add a
# further +0.1in buffer on top) so body content never overlaps the artwork.
HEADER_RESERVED_HEIGHT = 1.8 * inch
FOOTER_RESERVED_HEIGHT = 0.75 * inch


@lru_cache(maxsize=1)
def _full_letterhead_reader():
    """The whole letterhead artwork (header + watermark + footer)."""
    return ImageReader(LETTERHEAD_IMAGE_PATH)


@lru_cache(maxsize=1)
def _footer_band_reader():
    """Just the footer band (rule + trust-badge icons), cropped out of the
    full artwork for documents that build their own header as flowables
    and only want the footer repeated."""
    from PIL import Image as PILImage

    im = PILImage.open(LETTERHEAD_IMAGE_PATH)
    width, height = im.size
    top = int(height * _FOOTER_CROP_TOP_FRAC)
    cropped = im.crop((0, top, width, height))
    buf = BytesIO()
    cropped.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf), cropped.size


def _draw_page_number(canvas, doc, band_top):
    """Drawn just above the footer band — the badge captions inside the
    artwork run to the bottom page edge, so there's no clear space within
    the band itself."""
    left = 0.75 * inch
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED_TEXT)
    canvas.drawString(left, band_top + 3, f"{settings.COMPANY_NAME} — Page {doc.page}")


def draw_letterhead(canvas, doc):
    """Combined onFirstPage/onLaterPages callback: draws the full letterhead
    artwork (header, watermark and footer together) stretched over the
    entire page, then the page number on top."""
    canvas.saveState()
    page_width, page_height = doc.pagesize
    canvas.drawImage(
        _full_letterhead_reader(), 0, 0, width=page_width, height=page_height,
        preserveAspectRatio=False, mask='auto',
    )
    _draw_page_number(canvas, doc, page_height * (1 - _FOOTER_CROP_TOP_FRAC))
    canvas.restoreState()


def draw_letterhead_footer(canvas, doc):
    """Footer-only callback for documents that already build their own
    per-page company-identity header as flowables — draws just the footer
    band (rule + trust-badge icons), not the full-page artwork."""
    canvas.saveState()
    page_width, page_height = doc.pagesize
    reader, (crop_w, crop_h) = _footer_band_reader()
    band_height = page_width * (crop_h / crop_w)
    canvas.drawImage(
        reader, 0, 0, width=page_width, height=band_height,
        preserveAspectRatio=False, mask='auto',
    )
    _draw_page_number(canvas, doc, band_height)
    canvas.restoreState()
