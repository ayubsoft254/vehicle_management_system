from django.shortcuts import render

from .models import Company

# Safaricom keeps posting payments for a suspended company; record them
# rather than lose a customer's money.
ALWAYS_ALLOWED_PREFIXES = ('/health/', '/confirmation', '/validation', '/mpesa-callback',
                           '/payments/paybill/callbacks/', '/payments/paybill2/callbacks/',
                           '/payments/mpesa-callback',
                           '/static/', '/media/')


class CompanyStatusMiddleware:
    """Stop requests to a company that is suspended or still being set up.
    Runs right after django-tenants has picked the company from the host."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        company = getattr(request, 'tenant', None)
        if (company is not None and not company.is_platform
                and company.status != Company.STATUS_ACTIVE
                and not request.path.startswith(ALWAYS_ALLOWED_PREFIXES)):
            return render(request, 'tenancy/unavailable.html', {'company': company}, status=503)
        return self.get_response(request)
