import json

from django import template
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from apps.company.services import get_company
from utils.theme import is_default_primary, palette

register = template.Library()


@register.simple_tag
def tailwind_config():
    """The one Tailwind CDN config every page uses: the company's primary
    and accent palettes, plus blue/indigo remapped to the primary palette
    when the company colour isn't the default blue (so the many hardcoded
    blue-* classes follow the brand without template edits). Status colours
    (green, red, yellow…) are left alone."""
    brand = get_company()
    primary = {str(k): v for k, v in palette(brand.primary_color).items()}
    colors = {
        'primary': primary,
        'accent': {str(k): v for k, v in palette(brand.accent_color).items()},
    }
    if not is_default_primary(brand.primary_color):
        colors['blue'] = primary
        colors['indigo'] = primary
    config = {'theme': {'extend': {'colors': colors}}}
    # The same palettes as CSS variables, for page CSS that isn't Tailwind
    # classes: var(--brand-800), rgb(var(--brand-500-rgb) / 0.15), var(--accent-500)
    css_vars = []
    for prefix, shades in (('brand', colors['primary']), ('accent', colors['accent'])):
        for shade, hex_value in shades.items():
            r, g, b = (int(hex_value[i:i + 2], 16) for i in (1, 3, 5))
            css_vars.append(f'--{prefix}-{shade}:{hex_value};--{prefix}-{shade}-rgb:{r} {g} {b};')
    return mark_safe(f'<style>:root{{{"".join(css_vars)}}}</style>'
                     f'<script>tailwind.config = {json.dumps(config)};</script>')


@register.simple_tag
def payment_method_options(selected='', mixed=False):
    """<option>s for every active payment method (generic methods plus the
    company's account channels from Settings). Each carries data-group
    (hoza/ke/… or '') so scripts can subtotal by account group."""
    from apps.payments.channels import selectable_methods
    return format_html_join(
        '\n', '<option value="{}" data-group="{}"{}>{}</option>',
        ((m['code'], m['group'], mark_safe(' selected') if m['code'] == selected else '', m['label'])
         for m in selectable_methods(mixed=mixed)),
    )


@register.simple_tag
def currency_options(long_names=False, include='', selected=''):
    """<option>s for a currency picker: the company's base currency
    followed by the other currencies from Settings → Region, plus any
    comma-separated `include` codes (e.g. "KES,USD,JPY" for ledgers that
    must always offer those). `selected` defaults to the base currency."""
    from utils.currency import currency_name
    brand = get_company()
    codes = [(brand.currency_code, currency_name(brand.currency_code))]
    codes += [(o['code'], o['name']) for o in brand.currency_options]
    seen = {code for code, _ in codes}
    for code in (c.strip().upper() for c in str(include or '').split(',')):
        if len(code) == 3 and code not in seen:
            seen.add(code)
            codes.append((code, currency_name(code)))
    selected = str(selected or '').strip().upper()
    if selected not in seen:
        selected = brand.currency_code
    return format_html_join(
        '\n', '<option value="{}"{}>{}</option>',
        ((code, mark_safe(' selected') if code == selected else '', f'{code} — {name}' if long_names and name != code else code)
         for code, name in codes),
    )


@register.simple_tag
def get_brand():
    """`{% get_brand as brand %}` for templates rendered without a request
    (emails, HTML-to-PDF), where the context processor doesn't run."""
    return get_company()
