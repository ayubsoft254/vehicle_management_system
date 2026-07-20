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
    """Full acquisition + program cost for a vehicle, as a breakdown dict."""
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
        + (vehicle.commission_cost or ZERO)
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
    """Actual profit/loss for a completed sale: agreed selling price minus total cost.

    Revenue uses ClientVehicle.purchase_price - the field balance/total_paid
    and every other report (dashboard, financial reports) already treat as
    the authoritative sale price. final_selling_price is left blank (0) on
    most historical sales, so it isn't reliable here.
    """
    cost = compute_vehicle_total_cost(client_vehicle.vehicle)
    revenue = client_vehicle.purchase_price or ZERO
    profit = revenue - cost['total_cost']
    margin_percentage = (profit / cost['total_cost'] * 100) if cost['total_cost'] else ZERO

    return {
        **cost,
        'revenue': revenue,
        'profit': profit,
        'is_profit': profit >= ZERO,
        'margin_percentage': margin_percentage,
    }
