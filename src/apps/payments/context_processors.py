"""
Template context processors for the payments app.
"""


def pending_payment_requests(request):
    """Pending manual payments/reversals awaiting an admin, for the sidebar badge."""
    from utils.tenancy import on_platform_schema
    if on_platform_schema():
        return {}  # the platform control panel has no payments

    from .manual_payments import is_payment_approver
    from .models import PaymentRequest

    user = getattr(request, 'user', None)
    if not is_payment_approver(user):
        return {}
    return {
        'pending_payment_request_count': PaymentRequest.objects.filter(
            status=PaymentRequest.STATUS_PENDING
        ).count(),
    }
