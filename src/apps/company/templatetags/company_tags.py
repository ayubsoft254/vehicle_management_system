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
    return mark_safe(f'<script>tailwind.config = {json.dumps(config)};</script>')


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
def get_brand():
    """`{% get_brand as brand %}` for templates rendered without a request
    (emails, HTML-to-PDF), where the context processor doesn't run."""
    return get_company()
