"""
Currency names and approximate cross rates.

A company keeps its books in one base currency (Settings → Region) and can
offer other currencies for display and export (Settings → Region → Other
currencies), each with an optional fixed rate. Live rates come from the
browser (open.er-api.com, see static/js/multi_currency.js); the approximate
rates below are only a server-side fallback for exports when neither a live
nor a fixed rate is available.
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CURRENCY_NAMES = {
    'KES': 'Kenyan Shilling', 'UGX': 'Ugandan Shilling', 'TZS': 'Tanzanian Shilling',
    'RWF': 'Rwandan Franc', 'BIF': 'Burundian Franc', 'SSP': 'South Sudanese Pound',
    'ETB': 'Ethiopian Birr', 'CDF': 'Congolese Franc', 'SOS': 'Somali Shilling',
    'USD': 'US Dollar', 'EUR': 'Euro', 'GBP': 'British Pound', 'JPY': 'Japanese Yen',
    'CNY': 'Chinese Yuan', 'AED': 'UAE Dirham', 'INR': 'Indian Rupee', 'ZAR': 'South African Rand',
}

# Approximate value of one unit in KES — fallback only, see module docstring.
_KES_PER_UNIT = {
    'KES': Decimal('1'), 'USD': Decimal('130'), 'EUR': Decimal('142'), 'GBP': Decimal('165'),
    'JPY': Decimal('0.87'), 'CNY': Decimal('18'), 'AED': Decimal('35.4'), 'INR': Decimal('1.55'),
    'ZAR': Decimal('7.1'), 'TZS': Decimal('0.052'), 'UGX': Decimal('0.035'), 'RWF': Decimal('0.096'),
    'BIF': Decimal('0.045'), 'ETB': Decimal('1.05'), 'CDF': Decimal('0.046'), 'SSP': Decimal('0.03'),
    'SOS': Decimal('0.23'),
}

DEFAULT_OTHER_CURRENCIES = ['USD', 'EUR', 'TZS', 'UGX', 'JPY']


def currency_name(code):
    return CURRENCY_NAMES.get(code, code)


def approx_rate(base, code):
    """Approximate base-currency units per 1 `code`, or None if unknown."""
    if base == code:
        return Decimal('1')
    base_kes, code_kes = _KES_PER_UNIT.get(base), _KES_PER_UNIT.get(code)
    if not base_kes or not code_kes:
        return None
    return (code_kes / base_kes).quantize(Decimal('0.000001'))


def parse_rate(value):
    """A positive Decimal from user input, or None for blank/invalid."""
    try:
        rate = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None
    return rate if rate > 0 else None


def base_units_per(code, profile=None):
    """Base-currency units per 1 `code`: the company's fixed rate from
    Settings → Region when set, else the approximate one (None if unknown)."""
    if profile is None:
        from apps.company.services import get_company
        profile = get_company()
    if code == profile.currency_code:
        return Decimal('1')
    for option in profile.currency_options:
        if option['code'] == code and option['rate']:
            return option['rate']
    return approx_rate(profile.currency_code, code)


LEDGER_CURRENCIES = ('KES', 'USD', 'JPY')


def parse_display_currency(request, source=None):
    """(currency, factor) for printing amounts stored in `source` (default:
    the base currency) in the currency a page's picker selected —
    ?currency=XXX&currency_rate=n, the rate being target units per 1 source
    unit. Without a usable rate it falls back to the company's fixed rate,
    then an approximate one, then to `source` unconverted. Allowed targets:
    the source, the base, the configured currencies and LEDGER_CURRENCIES."""
    from apps.company.services import get_company
    profile = get_company()
    source = source or profile.currency_code
    target = (request.GET.get('currency') or source).strip().upper()
    allowed = {profile.currency_code, source, *LEDGER_CURRENCIES}
    allowed.update(o['code'] for o in profile.currency_options)
    if target == source or target not in allowed:
        return source, Decimal('1')

    rate = parse_rate(request.GET.get('currency_rate', ''))
    if rate:
        return target, rate

    from_base, to_base = base_units_per(source, profile), base_units_per(target, profile)
    if not from_base or not to_base:
        return source, Decimal('1')
    return target, (from_base / to_base).quantize(Decimal('0.00000001'))


# ── Foreign-currency entry (Japan supplier charges and payments) ────────────
# Staff can enter supplier amounts in any currency with a rate of
# "<currency> per 1 USD"; the ledger itself stays in USD.

FOREIGN_ENTRY_CURRENCIES = ['USD', 'JPY', 'KES', 'EUR', 'GBP', 'CNY', 'AED']


def parse_entry_currency(post_data, prefix):
    """(currency, rate per 1 USD) from <prefix>currency / <prefix>currency_other /
    <prefix>exchange_rate. Raises ValueError with a user-facing message."""
    code = (post_data.get(f'{prefix}currency') or 'USD').strip().upper()
    if code == 'OTHER':
        code = (post_data.get(f'{prefix}currency_other') or '').strip().upper()
    if not re.fullmatch(r'[A-Z]{3}', code):
        raise ValueError('Enter a valid 3-letter currency code (e.g. JPY).')
    if code == 'USD':
        return code, Decimal('1')
    rate = parse_rate(post_data.get(f'{prefix}exchange_rate', ''))
    if not rate:
        raise ValueError(f'Enter the exchange rate ({code} per 1 USD).')
    return code, rate.quantize(Decimal('0.000001'))


def to_usd(amount, rate):
    """Amount in a currency quoted at `rate` per 1 USD, as USD (2 dp, half-up)."""
    return (Decimal(amount) / Decimal(rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
