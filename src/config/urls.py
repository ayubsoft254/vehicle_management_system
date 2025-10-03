"""
Vehicle Management System - Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required

urlpatterns = [
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
    
    # Serve static files in development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
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