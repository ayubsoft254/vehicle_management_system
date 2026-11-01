"""
URLs for the platform domain (settings.PLATFORM_DOMAIN) in multi-company
mode: the control panel for platform owners. Company domains use
config/urls.py.
"""
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    return JsonResponse({'status': 'healthy', 'service': 'vehicle_management_system', 'scope': 'platform'})


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('', include(('apps.tenancy.urls', 'platform'), namespace='platform')),
]
