"""
Template context processors for the dashboard app.
"""
from apps.company.services import get_company, mpesa_setting
from apps.payments.channels import group_labels
from utils.theme import is_default_primary, palette, readable_text_on


def company_info(request):
    """
    Expose the company profile (Settings → Company & Branding) to every
    template as `brand`, its colour palettes as `theme`, plus the older
    company_* names templates already use.
    """
    brand = get_company()
    primary = palette(brand.primary_color)

    return {
        'brand': brand,
        'theme': {
            'primary': primary,
            'accent': palette(brand.accent_color),
            # Tailwind's blue/indigo utility classes are remapped to the
            # company colour only when it differs from the default blue.
            'remap_blue': not is_default_primary(brand.primary_color),
            'on_primary': readable_text_on(primary[600]),
        },
        'company_name': brand.legal_name,
        'company_phone': brand.phone,
        'company_phone_primary': brand.primary_phone,
        'company_phone_primary_tel': brand.primary_phone_tel,
        'company_email': brand.email,
        'company_address': brand.postal_address,
        'company_website': brand.website,
        'paybill_primary': mpesa_setting('MPESA_SHORTCODE'),
        'paybill_secondary': mpesa_setting('MPESA_SHORTCODE_2'),
        'channel_groups': group_labels(),
    }
