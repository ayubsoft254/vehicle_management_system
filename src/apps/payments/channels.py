"""
Payment channels as data.

The payment methods a cashier can pick are the generic ones below plus every
finance Account that has a payment_method_code (the company's bank and
mobile-money accounts), managed at Settings → Company & Branding →
Payments. Stored codes never change (equity_hoza etc. stay valid), so no
data migration is needed when a channel is renamed or disabled.

Model fields take these functions as callable `choices`, and the
*_CHOICES class attributes are lazy iterators over them, so
`dict(Payment.PAYMENT_METHOD_CHOICES)` always reflects the current accounts.
"""
from django.db import DatabaseError
from django.utils.choices import CallableChoiceIterator
from django.utils.text import slugify

GENERIC_BEFORE = [
    ('cash', 'Cash'),
    ('mpesa', 'M-Pesa'),
    ('bank_transfer', 'Bank Transfer'),
]
GENERIC_AFTER = [
    ('cheque', 'Cheque'),
    ('card', 'Credit/Debit Card'),
]
MIXED = ('mixed', 'Multiple Methods')
OTHER = ('other', 'Other')
GENERIC_CODES = {code for code, _ in GENERIC_BEFORE + GENERIC_AFTER + [MIXED, OTHER]}

# Used only when the accounts table can't be read (fresh database,
# mid-migration) — the channels every deployment had before they became data.
_FALLBACK_CHANNELS = [
    ('equity_hoza', 'Equity Hoza', 'hoza'),
    ('dib_hoza', 'DIB Hoza', 'hoza'),
    ('coop_hoza', 'COOP Hoza', 'hoza'),
    ('kcb_ke', 'KCB KE', 'ke'),
    ('absa_ke', 'ABSA KE', 'ke'),
    ('equity_ke', 'EQUITY KE', 'ke'),
]

GROUP_CODES = ('hoza', 'ke', 'cash', 'other')
DEFAULT_GROUP_LABELS = {'hoza': 'Hoza', 'ke': 'KE', 'cash': 'Cash', 'other': 'Other'}


def group_labels():
    """{group code: label}; labels are renamed per company in Settings."""
    from apps.company.services import get_company
    try:
        custom = get_company().channel_group_labels or {}
    except Exception:
        custom = {}
    return {code: (custom.get(code) or default) for code, default in DEFAULT_GROUP_LABELS.items()}


def group_label(code):
    return group_labels().get(code, code)


def group_choices():
    labels = group_labels()
    return [(code, labels[code]) for code in GROUP_CODES]


def _load_channels():
    from .models import Account
    try:
        qs = (Account.objects.exclude(payment_method_code__isnull=True)
              .exclude(payment_method_code='')
              .order_by('display_order', 'category', 'name'))
        return [(a.payment_method_code, a.name, a.category, a.is_active) for a in qs]
    except DatabaseError:
        return [(code, label, group, True) for code, label, group in _FALLBACK_CHANNELS]


def channels(active_only=False):
    """[(code, label, group)] for accounts usable as a payment method."""
    from apps.company.services import request_cached
    rows = request_cached('payment_channels', _load_channels)
    return [(code, label, group) for code, label, group, active in rows if active or not active_only]


def _with_generic(channel_rows, mixed):
    after = GENERIC_AFTER + ([MIXED] if mixed else []) + [OTHER]
    return GENERIC_BEFORE + [(code, label) for code, label, _g in channel_rows] + after


def payment_method_choices():
    """All methods incl. 'Multiple Methods' — Payment, PaymentSplit, PaymentRequest."""
    return _with_generic(channels(), mixed=True)


def payment_method_choices_single():
    """All methods except 'Multiple Methods' — deposits, trackers, insurance."""
    return _with_generic(channels(), mixed=False)


def withdrawal_method_choices():
    """Only the account channels — AccountWithdrawal."""
    return [(code, label) for code, label, _g in channels()]


def selectable_methods(mixed=False):
    """Active methods for <select> lists: [{'code', 'label', 'group'}]."""
    rows = [{'code': c, 'label': l, 'group': ''} for c, l in GENERIC_BEFORE]
    rows += [{'code': c, 'label': l, 'group': g} for c, l, g in channels(active_only=True)]
    after = GENERIC_AFTER + ([MIXED] if mixed else []) + [OTHER]
    rows += [{'code': c, 'label': l, 'group': ''} for c, l in after]
    return rows


def codes_in_group(group):
    return tuple(code for code, _l, g in channels() if g == group)


def group_of(method):
    """Group code of a payment method ('' for generic methods)."""
    for code, _l, g in channels():
        if code == method:
            return g
    return ''


def new_channel_code(name, group):
    """A unique, stable payment_method_code for a newly added channel."""
    from .models import Account
    base = slugify(f'{name} {group}').replace('-', '_')[:17] or 'channel'
    code, n = base, 2
    while code in GENERIC_CODES or Account.objects.filter(payment_method_code=code).exists():
        code = f'{base[:17 - len(str(n))]}_{n}'
        n += 1
    return code


# Proforma invoices store a short key for the payee bank account. These three
# keys pre-date bank accounts being data; other accounts use 'a<pk>'.
_LEGACY_PROFORMA_KEYS = {'equity_hoza': 'equity', 'dib_hoza': 'dib', 'coop_hoza': 'coop'}


def _proforma_key(account):
    return _LEGACY_PROFORMA_KEYS.get(account.payment_method_code or '') or f'a{account.pk}'


def proforma_accounts():
    from .models import Account
    try:
        return list(Account.objects.filter(show_on_proforma=True, is_active=True))
    except DatabaseError:
        return []


def proforma_account_choices():
    def label(a):
        return ' — '.join(filter(None, [a.bank_name or a.name, a.branch]))
    return [(_proforma_key(a), label(a)) for a in proforma_accounts()]


def proforma_account_details(key):
    """{'bank', 'branch', 'account_name', 'account_number'} for a stored
    proforma key, or None. Looks at inactive accounts too, so old proformas
    still print the account they were issued against."""
    from .models import Account
    if not key:
        return None
    account = None
    legacy_code = {v: k for k, v in _LEGACY_PROFORMA_KEYS.items()}.get(key)
    if legacy_code:
        account = Account.objects.filter(payment_method_code=legacy_code).first()
    elif key.startswith('a') and key[1:].isdigit():
        account = Account.objects.filter(pk=int(key[1:])).first()
    if account is None:
        return None
    return {
        'bank': account.bank_name or account.name,
        'branch': account.branch,
        'account_name': account.account_holder_name,
        'account_number': account.account_number,
    }


def customer_bank_details():
    """The bank account clients are told to pay into (client portal): the
    first active account marked "show on proforma" in Settings."""
    from apps.company.services import get_company
    accounts = proforma_accounts()
    account = accounts[0] if accounts else None
    return {
        'bank_name': (account.bank_name or account.name) if account else '',
        'account_name': (account.account_holder_name if account else '') or get_company().legal_name,
        'account_number': account.account_number if account else '',
        'branch': account.branch if account else '',
        'swift_code': '',
    }


PAYMENT_METHOD_CHOICES = CallableChoiceIterator(payment_method_choices)
SINGLE_METHOD_CHOICES = CallableChoiceIterator(payment_method_choices_single)
WITHDRAWAL_METHOD_CHOICES = CallableChoiceIterator(withdrawal_method_choices)
