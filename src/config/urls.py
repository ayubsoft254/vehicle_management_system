"""
Vehicle Management System - Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.payments import views as payment_views


@require_GET
def health_check(request):
    """Health check endpoint for Docker and load balancers"""
    return JsonResponse({'status': 'healthy', 'service': 'vehicle_management_system'})

urlpatterns = [
    # ============================================================================
    # HEALTH CHECK (for Docker and load balancers)
    # ============================================================================
    path('health/', health_check, name='health_check'),
    path('confirmation/', payment_views.paybill_confirmation_callback, name='paybill_confirmation_callback_root'),
    path('validation/', payment_views.paybill_validation_callback, name='paybill_validation_callback_root'),
    path('mpesa-callback/', payment_views.stk_push_callback, name='stk_push_callback_root'),

    # ============================================================================
    # PWA — service worker must be served from the root path so its scope
    # covers the whole site, not just /static/. See templates/pwa/service-worker.js.
    # ============================================================================
    path(
        'service-worker.js',
        TemplateView.as_view(template_name='pwa/service-worker.js', content_type='application/javascript'),
        name='service_worker',
    ),

    # ============================================================================
    # ADMIN
    # ============================================================================
    path('admin/', admin.site.urls),
    
    # ============================================================================
    # AUTHENTICATION
    # ============================================================================
    # Django Allauth authentication URLs
    path('accounts/', include('allauth.urls')),
    
    # Custom authentication URLs
    path('auth/', include('apps.authentication.urls')),
    
    # ============================================================================
    # CORE BUSINESS APPS
    # ============================================================================
    
    # Dashboard - Main interface
    path('', include('apps.dashboard.urls')),  # Landing page at root, dashboard at /dashboard/
    
    # Vehicles - Vehicle inventory management
    path('vehicles/', include('apps.vehicles.urls')),
    
    # Clients - Customer relationship management
    path('clients/', include('apps.clients.urls')),
    
    # ============================================================================
    # FINANCIAL MANAGEMENT APPS
    # ============================================================================
    
    # Payments - Payment processing and tracking
    path('payments/', include('apps.payments.urls')),
    
    # Expenses - Business expense tracking
    path('expenses/', include('apps.expenses.urls')),

    # Finance - Bank/cash account ledger and transaction control
    path('finance/', include('apps.finance.urls')),

    # Payroll - Employee compensation management
    path('payroll/', include('apps.payroll.urls')),
    
    # ============================================================================
    # OPERATIONAL APPS
    # ============================================================================
    
    # Auctions - Vehicle auction management
    path('auctions/', include('apps.auctions.urls')),
    
    # Insurance - Insurance policy and claims management
    path('insurance/', include('apps.insurance.urls')),
    
    # Repossessions - Vehicle repossession process management
    path('repossessions/', include('apps.repossessions.urls')),
    
    # ============================================================================
    # ADMINISTRATIVE APPS
    # ============================================================================
    
    # Reports - Business intelligence and reporting
    path('reports/', include('apps.reports.urls')),
    
    # Documents - Document management and storage
    path('documents/', include('apps.documents.urls')),
    
    # Notifications - System-wide notification management
    path('notifications/', include('apps.notifications.urls')),
    
    # ============================================================================
    # SECURITY & COMPLIANCE APPS
    # ============================================================================
    
    # Permissions - Role-based access control
    path('permissions/', include('apps.permissions.urls')),
    
    # Audit - System activity logging and compliance
    path('audit/', include('apps.audit.urls')),
    
    # ============================================================================
    # REDIRECTS
    # ============================================================================
    
    # Redirect root to dashboard if not already handled
    # path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
]

# ============================================================================
# ADMIN SITE CUSTOMIZATION
# ============================================================================

admin.site.site_header = "Vehicle Management System"
admin.site.site_title = "VMS Admin Portal"
admin.site.index_title = "Welcome to Vehicle Management System Administration"

# ============================================================================
# STATIC AND MEDIA FILES (Development Only)
# ============================================================================

if settings.DEBUG:
    # Serve media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Serve static files in development (WhiteNoise handles this in production)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # ============================================================================
    # MEDIA FILES IN PRODUCTION
    # ============================================================================
    # WhiteNoise only serves static files, not media files by default
    # We need to explicitly add media file serving for production
    # NOTE: For high-traffic sites, use cloud storage (S3, Azure Blob, etc.)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # ============================================================================
    # DEBUG TOOLBAR (Development Only)
    # ============================================================================
    
    # Django Debug Toolbar removed

# ============================================================================
# ERROR HANDLERS (Production)
# ============================================================================

# Custom error handlers
handler400 = 'apps.dashboard.views.bad_request'
handler403 = 'apps.dashboard.views.permission_denied'
handler404 = 'apps.dashboard.views.page_not_found'
handler500 = 'apps.dashboard.views.server_error'