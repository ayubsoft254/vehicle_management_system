import zoneinfo

from django.utils import timezone

from .services import begin_request, end_request, get_company


class CompanyMiddleware:
    """Start each request with a fresh company profile and activate the
    company's time zone, so Settings changes apply without a restart."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        begin_request()
        try:
            try:
                timezone.activate(zoneinfo.ZoneInfo(get_company().time_zone))
            except (zoneinfo.ZoneInfoNotFoundError, ValueError, TypeError):
                timezone.deactivate()
            return self.get_response(request)
        finally:
            timezone.deactivate()
            end_request()
