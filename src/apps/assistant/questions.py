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
from typing import Callable, List, Tuple

from django.utils import timezone

from apps.dashboard.utils import get_dashboard_overview_data, get_financial_summary


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
]

DEFAULT_SUGGESTIONS = [
    q for q in QUESTIONS
    if q.id in ('vehicle_counts', 'outstanding_balance', 'monthly_revenue', 'defaulters')
]
