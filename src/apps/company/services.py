"""
Access to the current company's profile.

get_company() is the one way code should read company identity, branding,
currency, letterhead or M-Pesa configuration. The profile is cached per
request (CompanyMiddleware clears it when each request starts) and for a few
seconds outside requests (Celery, management commands), and is dropped on
save, so Settings changes apply on the next request without a restart.
"""
import threading
import time

from django.conf import settings
from django.db import DatabaseError, connection
from django.utils.functional import lazy

_local = threading.local()
_OUTSIDE_REQUEST_TTL = 30  # seconds


def _schema():
    # One profile per company schema under django-tenants ("public" otherwise)
    return getattr(connection, 'schema_name', 'public') or 'public'


def clear_company_cache():
    _local.profiles = {}
    _local.cache = {}


def request_cached(key, compute):
    """Memoise compute() for the current request (or the same short TTL as
    the profile outside requests). Cleared with the company cache."""
    cache = getattr(_local, 'cache', None)
    if cache is None:
        cache = _local.cache = {}
    key = (_schema(), key)
    entry = cache.get(key)
    now = time.monotonic()
    if entry is not None and (getattr(_local, 'in_request', False) or now - entry[1] < _OUTSIDE_REQUEST_TTL):
        return entry[0]
    value = compute()
    cache[key] = (value, now)
    return value


def _fallback_profile():
    """Unsaved profile built from settings — used only before the
    company_profile table exists (fresh database, mid-migration)."""
    from .models import CompanyProfile
    return CompanyProfile(
        legal_name=getattr(settings, 'COMPANY_NAME', '') or 'My Company',
        short_name=getattr(settings, 'COMPANY_NAME', '') or 'My Company',
        postal_address=getattr(settings, 'COMPANY_ADDRESS', ''),
        phone=getattr(settings, 'COMPANY_PHONE', ''),
        email=getattr(settings, 'COMPANY_EMAIL', ''),
        website=getattr(settings, 'COMPANY_WEBSITE', ''),
        tax_pin=getattr(settings, 'COMPANY_PIN', ''),
    )


def get_company():
    from utils.tenancy import on_platform_schema
    if on_platform_schema():
        return _platform_profile()

    profiles = getattr(_local, 'profiles', None)
    if profiles is None:
        profiles = _local.profiles = {}
    schema = _schema()
    entry = profiles.get(schema)
    in_request = getattr(_local, 'in_request', False)
    if entry is not None and (in_request or time.monotonic() - entry[1] < _OUTSIDE_REQUEST_TTL):
        return entry[0]

    from .models import CompanyProfile
    try:
        profile = CompanyProfile.get_solo()
    except DatabaseError:
        return _fallback_profile()
    profiles[schema] = (profile, time.monotonic())
    return profile


def _platform_profile():
    """Identity shown on the platform control panel (no company profile
    table exists in the platform schema)."""
    from .models import CompanyProfile
    name = getattr(settings, 'PLATFORM_NAME', '') or 'Vehicle Platform'
    return CompanyProfile(legal_name=name, short_name=name, display_name=name, app_name=name)


def begin_request():
    clear_company_cache()
    _local.in_request = True


def end_request():
    _local.in_request = False
    clear_company_cache()


def currency():
    """The company's currency code, e.g. 'KES'."""
    return get_company().currency_code


def _with_currency(text):
    return text.replace('KES', currency())


# with_currency('Amount (KES)') — for labels/placeholders defined at import
# time; the code is substituted each time the text is rendered.
with_currency = lazy(_with_currency, str)


def _phone_example():
    return get_company().country_preset['phone_example']


# 'e.g. +254712345678 or 0712345678' for the company's country — lazy, for
# form placeholders/help texts defined at import time.
phone_example = lazy(_phone_example, str)


def mpesa_setting(key, default=''):
    """An M-Pesa setting: the Company Settings value when set, else the
    environment/settings.py value (which is how deployments were configured
    before Company Settings existed)."""
    value = ''
    use_server = False
    try:
        profile = get_company()
        value = profile.get_mpesa(key)
        use_server = profile.mpesa_use_server_settings
    except Exception:
        value = ''
    if value:
        return value
    # Only the original deployment falls back to the server's .env — a new
    # company must never pick up another company's paybill or callbacks.
    if use_server:
        return getattr(settings, key, default) or default
    if key == 'MPESA_RESULT_URL_BASE':
        # On the platform each company receives its callbacks on its own
        # main web address, so that's the natural default.
        return company_base_url() or default
    return default


def company_base_url():
    from utils.tenancy import multi_tenant
    tenant = getattr(connection, 'tenant', None)
    if not multi_tenant() or tenant is None or getattr(tenant, 'schema_name', 'public') == 'public':
        return ''
    domain = tenant.domains.filter(is_primary=True).first() or tenant.domains.first()
    if domain is None:
        return ''
    return f"{getattr(settings, 'PLATFORM_SCHEME', 'https')}://{domain.domain}"
