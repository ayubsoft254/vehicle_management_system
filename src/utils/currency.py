"""
Currency names and approximate cross rates.

A company keeps its books in one base currency (Settings → Region) and can
offer other currencies for display and export (Settings → Region → Other
currencies), each with an optional fixed rate. Live rates come from the
browser (open.er-api.com, see static/js/multi_currency.js); the approximate
rates below are only a server-side fallback for exports when neither a live
nor a fixed rate is available.
"""
from decimal import Decimal, InvalidOperation

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
