"""
Shared helpers for computing the actual profit/loss on a completed vehicle
sale, used by the Sales Ledger. Mirrors the "Actual Profit" calculation
already shown on the vehicle detail page (purchase price + duty + clearance
+ commission + extra costs + insurance + tracker + repossession costs,
against the agreed final selling price) so the two pages never disagree on
what a given sale actually made.
"""
from decimal import Decimal

from django.db.models import Q, Sum

ZERO = Decimal('0.00')


def compute_vehicle_total_cost(vehicle):
    """
    Full acquisition + program cost for a vehicle, as a breakdown dict.

    Deliberately does NOT include Vehicle.commission_cost - that field is
    legacy/unused (no longer entered during vehicle creation) and is not
    the real per-sale broker commission. Broker commission is a per-sale
    figure (ClientVehicle.commission_amount), added in compute_sale_profit()
    where the sale is known, not here.
    """
    extra_cost_total = vehicle.extra_costs.aggregate(total=Sum('amount'))['total'] or ZERO
    insurance_total = vehicle.insurance_policies.aggregate(total=Sum('buying_price'))['total'] or ZERO
    tracker_total = vehicle.expenses.filter(
        Q(category__name__icontains='track') | Q(category__code__icontains='TRACKER')
    ).aggregate(total=Sum('amount'))['total'] or ZERO
    repossession_cost_total = sum(
        (repo.get_total_additional_costs() for repo in vehicle.repossessions.all()),
        ZERO,
    )

    total_additional_cost = (
        (vehicle.duty_cost or ZERO)
        + (vehicle.clearance_cost or ZERO)
        + extra_cost_total
        + insurance_total
        + tracker_total
        + repossession_cost_total
    )
    total_cost = (vehicle.purchase_price or ZERO) + total_additional_cost

    return {
        'extra_cost_total': extra_cost_total,
        'insurance_total': insurance_total,
        'tracker_total': tracker_total,
        'repossession_cost_total': repossession_cost_total,
        'total_additional_cost': total_additional_cost,
        'total_cost': total_cost,
    }


def compute_sale_profit(client_vehicle):
    """Actual profit/loss for a single completed sale: agreed selling price minus
    total cost (including this sale's broker commission).

    Revenue uses ClientVehicle.purchase_price - the field balance/total_paid
    and every other report (dashboard, financial reports) already treat as
    the authoritative sale price. final_selling_price is left blank (0) on
    most historical sales, so it isn't reliable here.

    NOTE: if the same vehicle was sold more than once (e.g. repossessed and
    resold), each sale's row here carries that vehicle's full acquisition
    and program cost - correct for reading a single row in isolation, but
    summing this across multiple rows for the same vehicle double-counts
    that shared cost. Use bulk_sale_totals() for any aggregate total.
    """
    cost = compute_vehicle_total_cost(client_vehicle.vehicle)
    commission_amount = client_vehicle.commission_amount or ZERO
    total_cost = cost['total_cost'] + commission_amount
    revenue = client_vehicle.purchase_price or ZERO
    profit = revenue - total_cost
    margin_percentage = (profit / total_cost * 100) if total_cost else ZERO

    return {
        **cost,
        'commission_amount': commission_amount,
        'total_cost': total_cost,
        'revenue': revenue,
        'profit': profit,
        'is_profit': profit >= ZERO,
        'margin_percentage': margin_percentage,
    }


def bulk_sale_totals(client_vehicle_qs):
    """
    Bulk (no N+1) revenue/cost totals for a ClientVehicle queryset - the
    aggregate counterpart to compute_sale_profit(). Used for any *total*
    (dashboard KPI cards, Sales Ledger summary cards) rather than summing
    compute_sale_profit() per row, because a vehicle sold more than once
    would otherwise have its shared costs (purchase price, duty, clearance,
    extra costs, insurance, tracker, repossession) counted once per sale
    instead of once. Broker commission is the one cost that IS genuinely
    per-sale (ClientVehicle.commission_amount), so it's summed directly
    without deduplication.

    Each cost component is a separate .aggregate() call against its own
    model rather than one call joining every reverse relation at once, to
    avoid the classic Django fan-out (row-multiplying) bug from aggregating
    across multiple one-to-many joins in a single query.
    """
    from apps.insurance.models import InsurancePolicy
    from apps.expenses.models import Expense
    from apps.repossessions.models import Repossession, RepossessionExpense

    agg = client_vehicle_qs.aggregate(
        total_sales=Sum('purchase_price'),
        total_commission=Sum('commission_amount'),
    )
    total_sales = agg['total_sales'] or ZERO
    total_commission = agg['total_commission'] or ZERO

    # Deduplicated by vehicle - these costs belong to the vehicle, not to
    # any one sale of it, so a resold vehicle must only be counted once.
    vehicle_ids = list(set(client_vehicle_qs.values_list('vehicle_id', flat=True)))
    from .models import Vehicle, VehicleExtraCost

    vehicle_agg = Vehicle.objects.filter(id__in=vehicle_ids).aggregate(
        total_purchase=Sum('purchase_price'),
        total_duty=Sum('duty_cost'),
        total_clearance=Sum('clearance_cost'),
    )
    base_cost = (
        (vehicle_agg['total_purchase'] or ZERO)
        + (vehicle_agg['total_duty'] or ZERO)
        + (vehicle_agg['total_clearance'] or ZERO)
    )
    extra_costs = VehicleExtraCost.objects.filter(
        vehicle_id__in=vehicle_ids
    ).aggregate(t=Sum('amount'))['t'] or ZERO
    insurance_cost = InsurancePolicy.objects.filter(
        vehicle_id__in=vehicle_ids
    ).aggregate(t=Sum('buying_price'))['t'] or ZERO
    tracker_cost = Expense.objects.filter(
        related_vehicle_id__in=vehicle_ids
    ).filter(
        Q(category__name__icontains='track') | Q(category__code__icontains='TRACKER')
    ).aggregate(t=Sum('amount'))['t'] or ZERO
    repossession_cost = (
        (Repossession.objects.filter(vehicle_id__in=vehicle_ids).aggregate(t=Sum('total_cost'))['t'] or ZERO)
        + (RepossessionExpense.objects.filter(repossession__vehicle_id__in=vehicle_ids).aggregate(t=Sum('amount'))['t'] or ZERO)
    )

    total_cost = base_cost + total_commission + extra_costs + insurance_cost + tracker_cost + repossession_cost
    return total_sales, total_cost
