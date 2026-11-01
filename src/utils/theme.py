"""
Company colour theme helpers.

A company admin picks one primary and one accent colour on the Company
Settings page. Tailwind (and the PWA/PDFs) need a full 50-900 shade ladder,
so this module derives one from the picked colour, anchored at shade 600
(the shade buttons and links use).
"""
import re

DEFAULT_PRIMARY = '#2563eb'
DEFAULT_ACCENT = '#f97316'

SHADES = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900)

# Tailwind's own blue ladder — returned verbatim for the default colour so
# the existing look is pixel-identical.
_TAILWIND_BLUE = {
    50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
    500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
}

# How far each shade is mixed toward white (positive) or black (negative)
# from the shade-600 anchor. Tuned to land close to Tailwind's own ladders.
_MIX = {
    50: 0.94, 100: 0.86, 200: 0.72, 300: 0.54, 400: 0.32, 500: 0.14,
    600: 0.0, 700: -0.14, 800: -0.30, 900: -0.45,
}

_HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6})$')


def normalize_hex(value, default=DEFAULT_PRIMARY):
    match = _HEX_RE.match((value or '').strip())
    return f'#{match.group(1).lower()}' if match else default


def _rgb(hex_value):
    h = normalize_hex(hex_value).lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, round(c))):02x}' for c in rgb)


def palette(hex_value):
    """{50: '#...', ..., 900: '#...'} for a picked colour."""
    base = normalize_hex(hex_value)
    if base == DEFAULT_PRIMARY:
        return dict(_TAILWIND_BLUE)
    r, g, b = _rgb(base)
    shades = {}
    for shade in SHADES:
        mix = _MIX[shade]
        if mix >= 0:
            shades[shade] = _hex((c + (255 - c) * mix for c in (r, g, b)))
        else:
            shades[shade] = _hex((c * (1 + mix) for c in (r, g, b)))
    return shades


def is_default_primary(hex_value):
    return normalize_hex(hex_value) == DEFAULT_PRIMARY


def readable_text_on(hex_value):
    """'#ffffff' or '#111827', whichever reads better on the given colour."""
    r, g, b = _rgb(hex_value)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#111827' if luminance > 0.6 else '#ffffff'


def brand_hex(shade, default=None):
    """A shade of the current company's primary colour, for PDFs and other
    server-rendered output. `default` is returned unchanged while the company
    keeps the default blue, so existing documents stay exactly as they were."""
    from apps.company.services import get_company
    color = get_company().primary_color
    if default and is_default_primary(color):
        return default
    return palette(color)[shade]
