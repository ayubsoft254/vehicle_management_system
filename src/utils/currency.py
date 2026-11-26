"""
Server-side currency conversion for printed ledger statements.

Amounts are stored in KES (the Japan supplier ledger in USD). The on-screen
currency picker (static/js/multi_currency.js) uses live rates and passes the
rate it used to the PDF; the approximate rates below are only a fallback when
no rate is supplied.
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
