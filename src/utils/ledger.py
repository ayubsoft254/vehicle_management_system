"""
Shared double-entry-style statement builder.

Every ledger in the system presents transactions with separate Debit and
Credit columns, a running balance, and an opening/total-debit/total-credit/
closing summary. This helper turns a list of raw entries into that shape so
the client statement, party ledgers (broker, tracker agent, clearing agent,
Japan supplier, insurance agent), account ledgers and the main ledger all
agree on presentation and arithmetic.

Convention per ledger perspective:

* Receivable ledgers (client owes us): debit = charge/invoice,
  credit = payment received. Balance = debits - credits (what they owe).
* Payable ledgers (we owe the party): credit = bill/commission owed,
  debit = payment made to them. Balance = credits - debits (what we owe).
* Cash-book/account ledgers: debit = money received, credit = money paid
  out. Balance = opening + debits - credits.

An entry never carries the same amount in both the debit and credit column.
"""
import datetime as _dt
from decimal import Decimal

ZERO = Decimal('0.00')


def parse_date_range(request):
    """Read date_from/date_to GET params as date objects (or None each).

    Shared by every party/agent ledger detail view so the on-screen filter,
    the printed report and the running balance all agree on what "a specific
    date range or a specific date" means (from == to selects a single day).
    """
    def _parse(key):
        raw = request.GET.get(key, '').strip()
        if not raw:
            return None
        try:
            return _dt.date.fromisoformat(raw)
        except ValueError:
            return None
    return _parse('date_from'), _parse('date_to')


def make_entry(date, description, *, debit=ZERO, credit=ZERO, reference='',
               method='', related='', created_by=None, status='', notes='',
               detail_url=None, sort_key=None, document_url=None,
               is_reversed=False):
    """A single statement line. Exactly one of debit/credit should be set."""
    debit = debit or ZERO
    credit = credit or ZERO
    if debit and credit:
        raise ValueError(
            'A ledger entry cannot carry the same transaction in both the '
            'debit and credit columns.'
        )
    return {
        'date': date,
        'sort_key': sort_key if sort_key is not None else date,
        'reference': reference or '',
        'description': description,
        'method': method or '',
        'related': related or '',
        'debit': ZERO if is_reversed else debit,
        'credit': ZERO if is_reversed else credit,
        'display_amount': debit or credit,
        'created_by': created_by,
        'status': status or '',
        'notes': notes or '',
        'detail_url': detail_url,
        'document_url': document_url,
        'is_reversed': is_reversed,
    }


def build_statement(entries, *, opening_balance=ZERO, balance_from='debit'):
    """
    Sort entries chronologically, compute the running balance and totals.

    balance_from='debit'  -> balance grows with debits  (receivables, cash book)
    balance_from='credit' -> balance grows with credits (payables)

    Returns (rows_newest_first, summary) where summary carries
    opening_balance / total_debits / total_credits / closing_balance.
    """
    rows = sorted(entries, key=lambda e: (e['date'], str(e['sort_key'])))

    running = opening_balance
    total_debits = ZERO
    total_credits = ZERO
    for row in rows:
        total_debits += row['debit']
        total_credits += row['credit']
        if balance_from == 'credit':
            running += row['credit'] - row['debit']
        else:
            running += row['debit'] - row['credit']
        row['running_balance'] = running

    summary = {
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': running,
        'entry_count': len(rows),
        'balance_from': balance_from,
    }

    rows.reverse()
    return rows, summary
