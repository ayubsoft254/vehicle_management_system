"""
Template context processors for the dashboard app.
"""
from django.conf import settings


def company_info(request):
    """
    Expose the official company contact details (settings.COMPANY_*) to every
    template, so public-facing pages don't drift from hardcoded, stale values.
    """
    phone = getattr(settings, 'COMPANY_PHONE', '') or ''
    primary_phone = phone.split('/')[0].strip()

    return {
        'company_name': getattr(settings, 'COMPANY_NAME', ''),
        'company_phone': phone,
        'company_phone_primary': primary_phone,
        'company_phone_primary_tel': ''.join(ch for ch in primary_phone if ch.isdigit() or ch == '+'),
        'company_email': getattr(settings, 'COMPANY_EMAIL', ''),
        'company_address': getattr(settings, 'COMPANY_ADDRESS', ''),
        'company_website': getattr(settings, 'COMPANY_WEBSITE', ''),
    }
