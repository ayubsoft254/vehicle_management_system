"""
Server-side currency conversion for printed ledger statements.

Amounts are stored in KES (the Japan supplier ledger in USD). The on-screen
currency picker (static/js/multi_currency.js) uses live rates and passes the
rate it used to the PDF; the approximate rates below are only a fallback when
no rate is supplied.
"""
from decimal import Decimal, InvalidOperation

# Approximate value of one unit in KES — fallback only, see module docstring.
# Mirrors apps/payments/views.py::_EXPORT_CURRENCY_FALLBACK_RATES.
KES_PER_UNIT = {
    'KES': Decimal('1'),
    'USD': Decimal('130'),
    'EUR': Decimal('142'),
    'JPY': Decimal('0.87'),
    'TZS': Decimal('0.052'),
    'UGX': Decimal('0.035'),
}


def parse_rate(value):
    """A positive Decimal from user input, or None for blank/invalid."""
    try:
        rate = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None
    return rate if rate > 0 else None


def parse_display_currency(request, source='KES'):
    """(currency, factor) for printing amounts stored in `source` in the
    currency a page's picker selected — ?currency=XXX&currency_rate=n, the
    rate being target units per 1 source unit. Without a usable rate it
    falls back to the approximate KES_PER_UNIT cross rate; unknown
    currencies print in `source` unconverted."""
    target = (request.GET.get('currency') or source).strip().upper()
    if target == source or target not in KES_PER_UNIT or source not in KES_PER_UNIT:
        return source, Decimal('1')

    rate = parse_rate(request.GET.get('currency_rate', ''))
    if rate:
        return target, rate
    return target, (KES_PER_UNIT[source] / KES_PER_UNIT[target]).quantize(Decimal('0.00000001'))
