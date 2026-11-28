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
# Staff enter supplier amounts in any currency with a direct rate,
# "1 <currency> = <rate> <rate currency>" (e.g. 1 JPY = 0.82 KES). The supplier
# ledger itself stays in USD, so the rate currency's USD value comes from the
# page's own USD rate for the home currency, else the live rate the browser
# posts (<prefix>quote_usd).

FOREIGN_ENTRY_CURRENCIES = ['USD', 'JPY', 'KES', 'EUR', 'GBP', 'CNY', 'AED']
_CODE_RE = re.compile(r'[A-Z]{3}')


def parse_entry_currency(post_data, prefix, home='KES', home_usd_rate=None):
    """(currency, rate_currency, rate, usd_per_unit) from <prefix>currency /
    <prefix>currency_other / <prefix>exchange_rate / <prefix>rate_currency /
    <prefix>quote_usd. `home_usd_rate` is an on-page "1 USD = x <home>" rate.
    Raises ValueError with a user-facing message."""
    code = (post_data.get(f'{prefix}currency') or 'USD').strip().upper()
    if code == 'OTHER':
        code = (post_data.get(f'{prefix}currency_other') or '').strip().upper()
    if not _CODE_RE.fullmatch(code):
        raise ValueError('Enter a valid 3-letter currency code (e.g. JPY).')
    if code == 'USD':
        return 'USD', 'USD', Decimal('1'), Decimal('1')

    quote = (post_data.get(f'{prefix}rate_currency') or home or 'USD').strip().upper()
    if not _CODE_RE.fullmatch(quote):
        raise ValueError('Choose the currency the exchange rate converts to.')
    if quote == code:
        rate = Decimal('1')
    else:
        rate = parse_rate(post_data.get(f'{prefix}exchange_rate', ''))
        if not rate:
            raise ValueError(f'Enter the exchange rate (1 {code} = ? {quote}).')
        rate = rate.quantize(Decimal('0.0000000001'))

    home_rate = parse_rate(home_usd_rate) if home_usd_rate is not None else None
    if quote == 'USD':
        usd_per_quote = Decimal('1')
    elif quote == home and home_rate:
        usd_per_quote = Decimal('1') / home_rate
    else:
        usd_per_quote = parse_rate(post_data.get(f'{prefix}quote_usd', ''))
        if not usd_per_quote:
            raise ValueError(
                f'Could not get a live {quote} rate to post this to the supplier ledger. '
                'Check your connection and try again.'
            )
    return code, quote, rate, rate * usd_per_quote


def to_usd(amount, usd_per_unit):
    """Amount worth `usd_per_unit` USD per unit, as USD (2 dp, half-up)."""
    return (Decimal(amount) * Decimal(usd_per_unit)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
