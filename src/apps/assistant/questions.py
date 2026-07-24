"""
Assistant App - Canned Question Registry

Each Question maps a set of natural-language phrasings to a handler that
answers using the same aggregation functions the dashboard already uses
(apps.dashboard.utils). There is no LLM involved - free text is fuzzy
matched (see matching.py) against the `keywords` below.
"""

import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Callable, List, Optional, Tuple

from django.db.models import Q
from django.utils import timezone

from apps.dashboard.utils import get_dashboard_overview_data, get_financial_summary
from .text_utils import content_tokens


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str            # canonical phrasing, shown as a suggestion chip
    keywords: tuple         # phrases used for fuzzy matching
    handler: Callable[[str], str]


def _money(value) -> str:
    return f"KES {float(value or 0):,.2f}"


def _parse_period(text: str) -> Tuple[object, object, str]:
    """Return (date_from, date_to, label) for a period-scoped question."""
    text = text.lower()
    today = timezone.now().date()

    if 'today' in text:
        return today, today, 'today'
    if 'yesterday' in text:
        y = today - timedelta(days=1)
        return y, y, 'yesterday'

    days_match = re.search(r'last (\d+)\s*days?', text)
    if days_match:
        n = int(days_match.group(1))
        return today - timedelta(days=n), today, f'the last {n} days'

    if 'last month' in text:
        first_of_this_month = today.replace(day=1)
        last_day_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_day_prev_month.replace(day=1)
        return first_of_prev_month, last_day_prev_month, 'last month'

    if 'this week' in text:
        start = today - timedelta(days=today.weekday())
        return start, today, 'this week'

    # default: this month
    return today.replace(day=1), today, 'this month'


# ============================================================================
# HANDLERS
# ============================================================================

def _handle_vehicle_counts(text: str) -> str:
    v = get_dashboard_overview_data()['vehicles']
    return (
        f"{v['total']} vehicles total — {v['available']} available, "
        f"{v['reserved']} reserved, {v['sold']} sold, "
        f"{v['maintenance']} in maintenance, {v['repossessed']} repossessed."
    )


def _handle_overstayed_vehicles(text: str) -> str:
    data = get_dashboard_overview_data()
    count = data['overstayed_vehicles_count']
    if not count:
        return "No vehicles have been sitting in inventory for more than 6 months."
    names = ', '.join(v['vehicle_name'] for v in data['overstayed_vehicles'][:5])
    extra = f" and {count - 5} more" if count > 5 else ""
    return f"{count} vehicle(s) have been in inventory over 6 months: {names}{extra}."


def _handle_client_counts(text: str) -> str:
    c = get_dashboard_overview_data()['clients']
    return f"{c['total']} clients total, {c['active']} active, {c['new_today']} registered today."


def _handle_revenue_today(text: str) -> str:
    p = get_dashboard_overview_data()['payments']
    return f"Collected {_money(p['total_today'])} today across {p['count_today']} payment(s)."


def _handle_monthly_revenue(text: str) -> str:
    p = get_dashboard_overview_data()['payments']
    return f"{_money(p['monthly_revenue'])} collected so far this month ({_money(p['all_time'])} all-time)."


def _handle_outstanding(text: str) -> str:
    o = get_dashboard_overview_data()['outstanding']
    return (
        f"{_money(o['total'])} outstanding across {o['active_accounts']} active installment account(s). "
        f"{_money(o['overdue_total'])} of that is overdue across {o['overdue_schedules']} schedule(s)."
    )


def _handle_defaulters(text: str) -> str:
    defaulters = get_dashboard_overview_data()['defaulters']
    if not defaulters:
        return "No clients are currently overdue on payments."
    lines = [
        f"{d['client_name']} — {_money(d['overdue_amount'])} ({d['days_overdue']} days overdue)"
        for d in defaulters[:5]
    ]
    extra = f", and {len(defaulters) - 5} more" if len(defaulters) > 5 else ""
    return "Top overdue clients: " + "; ".join(lines) + extra + "."


def _handle_sales(text: str) -> str:
    s = get_dashboard_overview_data()['sales']
    return (
        f"{s['total_count']} vehicles sold for {_money(s['total_revenue'])} total "
        f"({s['monthly_count']} this month for {_money(s['monthly_revenue'])}). "
        f"Collection rate: {s['collection_rate_percent']}%."
    )


def _handle_profit(text: str) -> str:
    p = get_dashboard_overview_data()['profit']
    status = "profitable" if p['is_profitable'] else "operating at a loss"
    return f"{_money(p['total'])} profit all-time ({status}); {_money(p['monthly'])} this month."


def _handle_top_makes(text: str) -> str:
    makes = get_dashboard_overview_data()['most_sold_makes']
    if not makes:
        return "No sales recorded yet."
    lines = [f"{m['make'] or 'Unknown'} ({m['count']} sold, {_money(m['revenue'])})" for m in makes]
    return "Best-selling makes: " + ", ".join(lines) + "."


def _handle_recent_sales(text: str) -> str:
    sales = get_dashboard_overview_data()['recent_sales']
    if not sales:
        return "No sales recorded yet."
    lines = [f"{s['vehicle_name']} to {s['client_name']} for {_money(s['purchase_price'])}" for s in sales[:5]]
    return "Most recent sales: " + "; ".join(lines) + "."


def _handle_expenses(text: str) -> str:
    date_from, date_to, label = _parse_period(text)
    data = get_financial_summary(date_from, date_to)
    return (
        f"{_money(data['total_expenses'])} in expenses {label} across {data['expense_count']} entries "
        f"(revenue was {_money(data['total_revenue'])}, net {_money(data['net_profit'])})."
    )


def _handle_auctions(text: str) -> str:
    a = get_dashboard_overview_data()['auctions']
    return f"{a['active']} active auction(s), {a['scheduled']} scheduled, {a['completed_today']} completed today."


def _handle_insurance(text: str) -> str:
    i = get_dashboard_overview_data()['insurance']
    return (
        f"{i['total']} insurance polic(ies) — {i['fully_paid']} fully paid, "
        f"{i['partially_paid']} partially paid, {i['unpaid']} unpaid. "
        f"{_money(i['balance_value'])} outstanding."
    )


def _handle_trackers(text: str) -> str:
    t = get_dashboard_overview_data()['trackers']
    return (
        f"{t['total']} tracker(s) installed — {t['fully_paid']} fully paid, "
        f"{t['partially_paid']} partially paid, {t['unpaid']} unpaid. "
        f"{_money(t['balance_value'])} outstanding."
    )


def _handle_daily_summary(text: str) -> str:
    d = get_dashboard_overview_data()['daily']
    return (
        f"Today ({d['date']}): expected {_money(d['expected_today'])}, "
        f"collected {_money(d['money_in'])} from {d['money_in_count']} payment(s), "
        f"spent {_money(d['money_out'])} on expenses. "
        f"{d['defaulters_count']} client(s) are currently overdue."
    )


def _handle_payroll_summary(text: str) -> str:
    from apps.payroll.utils import get_payroll_dashboard_stats
    s = get_payroll_dashboard_stats()
    parts = [
        f"{s['active_employees']} active employee(s) ({s['total_employees']} total).",
        f"{s['pending_leaves']} pending leave request(s), {s['pending_loans']} pending loan(s), "
        f"{s['pending_commissions']} pending commission(s).",
    ]
    current = s.get('current_payroll')
    if current:
        parts.append(
            f"This month's payroll ({current['status']}): {current['employees']} employee(s), "
            f"net {_money(current['total_net'])}."
        )
    else:
        parts.append("No payroll run exists for this month yet.")
    return " ".join(parts)


def _handle_repossessions_summary(text: str) -> str:
    from apps.repossessions.utils import get_repossession_dashboard_stats
    s = get_repossession_dashboard_stats()
    return (
        f"{s['total_active']} active repossession case(s) — {s['pending_approval']} pending approval, "
        f"{s['in_recovery']} in recovery, {s['vehicles_recovered']} vehicle(s) recovered. "
        f"{_money(s['total_outstanding'])} outstanding, {_money(s['total_recovery_costs'])} spent on recovery. "
        f"{s['overdue_notices']} notice(s) overdue."
    )


def _handle_recent_activity(text: str) -> str:
    from apps.audit.utils import get_recent_activity
    logs = list(get_recent_activity(days=7)[:5])
    if not logs:
        return "No recorded system activity in the last 7 days."
    lines = []
    for log in logs:
        actor = log.user.get_full_name() if log.user else 'System'
        action = log.get_action_display() if hasattr(log, 'get_action_display') else log.action
        lines.append(f"{actor} {action.lower()} — {log.description}")
    return "Recent activity: " + "; ".join(lines) + "."


def _handle_documents_summary(text: str) -> str:
    from apps.documents.models import Document
    total = Document.objects.count()
    active = Document.objects.filter(is_active=True).count()
    recent = Document.objects.filter(uploaded_at__gte=timezone.now() - timedelta(days=7)).count()
    return f"{total} document(s) on file ({active} active), {recent} uploaded in the last 7 days."


def _handle_reports_summary(text: str) -> str:
    from apps.reports.models import Report
    total = Report.objects.count()
    active = Report.objects.filter(is_active=True).count()
    return f"{active} active report definition(s) out of {total} total."


# ============================================================================
# ENTITY LOOKUPS (vehicle by plate/VIN, client by name)
#
# These answer questions about ONE specific record rather than an
# aggregate, so they carry a free-form identifier (a plate number, a
# person's name) that will never appear in a fixed keyword list. The
# fuzzy matcher in matching.py penalizes exactly that kind of unmatched
# extra content, so these are detected separately in try_entity_lookup()
# and checked before the fuzzy matcher runs at all - see views.ask().
# ============================================================================

_CLIENT_LOOKUP_EXTRA_STOPWORDS = frozenset({
    'client', 'clients', 'customer', 'customers', 'owe', 'owes', 'owed',
    'balance', 'payment', 'payments', 'history', 'status', 'about',
})
_DEBT_TRIGGER_WORDS = ('owe', 'owes', 'owed', 'outstanding', 'balance', 'client', 'customer')


def _find_vehicle(text: str):
    """Best-effort lookup by registration number or VIN, tolerant of
    stray spaces/punctuation and surrounding words ("what's up with KAA
    123B" still finds KAA123B)."""
    from apps.vehicles.models import Vehicle

    compact_query = re.sub(r'[^A-Za-z0-9]', '', text).upper()
    if len(compact_query) < 4 or not any(c.isdigit() for c in compact_query):
        return None  # cheap bail-out: every real plate/VIN here has a digit

    vin_fallback = None
    for vehicle in Vehicle.objects.all().only(
        'id', 'registration_number', 'vin', 'make', 'model', 'year', 'status'
    ):
        reg_compact = re.sub(r'[^A-Za-z0-9]', '', vehicle.registration_number or '').upper()
        if reg_compact and len(reg_compact) >= 4 and reg_compact in compact_query:
            return vehicle
        if vin_fallback is None:
            vin_compact = re.sub(r'[^A-Za-z0-9]', '', vehicle.vin or '').upper()
            if vin_compact and len(vin_compact) >= 6 and vin_compact in compact_query:
                vin_fallback = vehicle
    return vin_fallback


def _describe_vehicle(vehicle) -> str:
    parts = [
        f"{vehicle.full_name} ({vehicle.registration_number or vehicle.vin}) "
        f"is {vehicle.get_status_display()}."
    ]
    sale = vehicle.client_purchases.select_related('client').order_by('-purchase_date').first()
    if sale:
        paid_note = " (paid off)" if sale.is_paid_off else f", balance {_money(sale.balance)}"
        parts.append(f"Sold to {sale.client.get_full_name()} for {_money(sale.purchase_price)}{paid_note}.")
    return " ".join(parts)


def _extract_name_query(text: str) -> str:
    tokens = content_tokens(text, _CLIENT_LOOKUP_EXTRA_STOPWORDS)
    return ' '.join(sorted(tokens))


def _find_client(text: str):
    from apps.clients.models import Client

    query = _extract_name_query(text)
    parts = [p for p in query.split() if len(p) >= 2]
    if not parts:
        return None

    name_filter = Q()
    for part in parts:
        name_filter |= Q(first_name__icontains=part) | Q(last_name__icontains=part)

    candidates = list(Client.objects.filter(name_filter).distinct()[:25])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Prefer a candidate whose full name contains every extracted token -
    # disambiguates when multiple clients share a first or last name.
    for candidate in candidates:
        full_name = f"{candidate.first_name} {candidate.last_name}".lower()
        if all(part in full_name for part in parts):
            return candidate
    return candidates[0]


def _describe_client(client) -> str:
    purchases = client.vehicles.select_related('vehicle').order_by('-purchase_date')
    contact = client.phone_primary or 'no phone on file'
    if not purchases.exists():
        return f"{client.get_full_name()} ({contact}) has no vehicle purchases on record."

    lines = []
    total_owed = Decimal('0.00')
    for cv in purchases[:3]:
        if cv.is_paid_off:
            lines.append(f"{cv.vehicle.full_name} — paid off")
        else:
            lines.append(f"{cv.vehicle.full_name} — owes {_money(cv.balance)}")
            total_owed += cv.balance or Decimal('0.00')

    summary = f"{client.get_full_name()} ({contact}): " + "; ".join(lines) + "."
    if total_owed > 0:
        summary += f" Total outstanding: {_money(total_owed)}."
    return summary


def _handle_vehicle_lookup(text: str) -> str:
    vehicle = _find_vehicle(text)
    if not vehicle:
        return "I couldn't find a vehicle matching that plate or VIN. Try the exact registration, e.g. 'KAA123B'."
    return _describe_vehicle(vehicle)


def _handle_client_lookup(text: str) -> str:
    client = _find_client(text)
    if not client:
        return "I couldn't find a client matching that name. Try their full name, e.g. 'John Kamau'."
    return _describe_client(client)


def try_entity_lookup(text: str) -> Optional[Tuple[str, str]]:
    """
    Best-effort direct entity lookup, checked before the general fuzzy
    matcher (see views.ask()). Returns (question_id, answer) or None.

    A recognizable plate/VIN is checked unconditionally - it's a strong,
    unambiguous signal on its own. A client-name lookup is gated behind a
    debt/identity trigger word so an unrelated two-word phrase doesn't
    get misread as somebody's name.
    """
    vehicle = _find_vehicle(text)
    if vehicle:
        return 'vehicle_lookup', _describe_vehicle(vehicle)

    lowered = text.lower()
    if any(word in lowered for word in _DEBT_TRIGGER_WORDS):
        client = _find_client(text)
        if client:
            return 'client_lookup', _describe_client(client)

    return None


# ============================================================================
# REGISTRY
# ============================================================================

QUESTIONS: List[Question] = [
    Question(
        id='vehicle_counts',
        prompt="How many vehicles do we have?",
        keywords=("how many vehicles", "how many cars do we have", "how many vehicles do we have", "vehicle count", "vehicles available", "inventory count", "cars in stock"),
        handler=_handle_vehicle_counts,
    ),
    Question(
        id='overstayed_vehicles',
        prompt="Which vehicles have been in stock too long?",
        keywords=("overstayed vehicles", "vehicles in stock too long", "aging inventory", "old stock", "slow moving vehicles"),
        handler=_handle_overstayed_vehicles,
    ),
    Question(
        id='client_counts',
        prompt="How many clients do we have?",
        keywords=("how many clients", "client count", "active clients", "new clients today", "total customers"),
        handler=_handle_client_counts,
    ),
    Question(
        id='revenue_today',
        prompt="How much have we collected today?",
        keywords=("revenue today", "collected today", "payments today", "money in today", "how much did we make today"),
        handler=_handle_revenue_today,
    ),
    Question(
        id='monthly_revenue',
        prompt="What's our revenue this month?",
        keywords=("monthly revenue", "revenue this month", "how much have we made this month", "total revenue all time"),
        handler=_handle_monthly_revenue,
    ),
    Question(
        id='outstanding_balance',
        prompt="How much do clients owe us in total?",
        keywords=("outstanding balance", "how much do clients owe", "who owes us money", "total owed", "money outside", "amount pending"),
        handler=_handle_outstanding,
    ),
    Question(
        id='defaulters',
        prompt="Which clients are overdue on payments?",
        keywords=("overdue clients", "defaulters", "who is behind on payments", "late payments", "clients overdue"),
        handler=_handle_defaulters,
    ),
    Question(
        id='sales_summary',
        prompt="How many vehicles have we sold?",
        keywords=("vehicles sold", "total sales", "sales this month", "how many vehicles have we sold", "sales revenue"),
        handler=_handle_sales,
    ),
    Question(
        id='profit_summary',
        prompt="What's our profit?",
        keywords=("profit", "how much profit", "profit this month", "are we profitable", "net profit"),
        handler=_handle_profit,
    ),
    Question(
        id='top_makes',
        prompt="What are our best-selling makes?",
        keywords=("best selling makes", "top selling cars", "most sold makes", "popular vehicle brands", "most sold cars"),
        handler=_handle_top_makes,
    ),
    Question(
        id='recent_sales',
        prompt="What are the most recent sales?",
        keywords=("recent sales", "latest sales", "last vehicles sold", "who bought recently"),
        handler=_handle_recent_sales,
    ),
    Question(
        id='expenses',
        prompt="What were our expenses this month?",
        keywords=("expenses", "how much did we spend", "spending this month", "expenses last month", "money out"),
        handler=_handle_expenses,
    ),
    Question(
        id='auctions',
        prompt="What's the status of our auctions?",
        keywords=("auctions", "active auctions", "scheduled auctions", "auction status"),
        handler=_handle_auctions,
    ),
    Question(
        id='insurance',
        prompt="What's our insurance policy status?",
        keywords=("insurance", "insurance policies", "insurance balance", "unpaid insurance"),
        handler=_handle_insurance,
    ),
    Question(
        id='trackers',
        prompt="What's the status of our vehicle trackers?",
        keywords=("trackers", "tracker status", "tracker balance", "gps trackers"),
        handler=_handle_trackers,
    ),
    Question(
        id='daily_summary',
        prompt="Give me today's summary.",
        keywords=("today's summary", "daily report", "daily summary", "how's today looking", "end of day report"),
        handler=_handle_daily_summary,
    ),
    Question(
        id='payroll_summary',
        prompt="How's payroll looking this month?",
        keywords=("payroll", "payroll summary", "how's payroll looking", "pending leave requests", "pending loans", "employee count", "payroll status"),
        handler=_handle_payroll_summary,
    ),
    Question(
        id='repossessions_summary',
        prompt="What's the status of repossessions?",
        keywords=("repossessions", "repossession status", "active repossessions", "vehicles being recovered", "repossession cases"),
        handler=_handle_repossessions_summary,
    ),
    Question(
        id='recent_activity',
        prompt="What's happened recently in the system?",
        keywords=("recent activity", "audit log", "what happened recently", "system activity", "recent changes"),
        handler=_handle_recent_activity,
    ),
    Question(
        id='documents_summary',
        prompt="How many documents do we have on file?",
        keywords=("documents on file", "how many documents", "document count", "recently uploaded documents"),
        handler=_handle_documents_summary,
    ),
    Question(
        id='reports_summary',
        prompt="How many reports do we have set up?",
        keywords=("reports set up", "active reports", "how many reports", "report definitions"),
        handler=_handle_reports_summary,
    ),
    Question(
        id='vehicle_lookup',
        prompt="Tell me about vehicle KAA123B",
        keywords=("vehicle status", "tell me about vehicle", "look up vehicle", "vehicle details", "check registration"),
        handler=_handle_vehicle_lookup,
    ),
    Question(
        id='client_lookup',
        prompt="What does John Kamau owe?",
        keywords=("what does client owe", "client balance", "payment history for client", "how much does client owe"),
        handler=_handle_client_lookup,
    ),
]

DEFAULT_SUGGESTIONS = [
    q for q in QUESTIONS
    if q.id in ('vehicle_counts', 'outstanding_balance', 'monthly_revenue', 'defaulters')
]
