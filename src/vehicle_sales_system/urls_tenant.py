"""
URL Configuration for Tenant Schemas (Tenant-specific)
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication (Django Allauth)
    path('accounts/', include('allauth.urls')),
    
    # Core App (Dashboard, Profile, etc.)
    path('', include('core.urls', namespace='core')),
    
    # Vehicle Management
    # path('vehicles/', include('vehicles.urls', namespace='vehicles')),
    
    # Client Management
    # path('clients/', include('clients.urls', namespace='clients')),
    
    # Payment Management
    # path('payments/', include('payments.urls', namespace='payments')),
    
    # Payroll Management
    # path('payroll/', include('payroll.urls', namespace='payroll')),
    
    # Expense Tracking
    # path('expenses/', include('expenses.urls', namespace='expenses')),
    
    # Repossessions
    # path('repossessions/', include('repossessions.urls', namespace='repossessions')),
    
    # Auctions
    # path('auctions/', include('auctions.urls', namespace='auctions')),
    
    # Insurance
    # path('insurance/', include('insurance.urls', namespace='insurance')),
    
    # Notifications
    # path('notifications/', include('notifications.urls', namespace='notifications')),
    
    # Documents
    # path('documents/', include('documents.urls', namespace='documents')),
    
    # Reports
    # path('reports/', include('reports.urls', namespace='reports')),
    
    # Audit Logs
    # path('audit/', include('audit.urls', namespace='audit')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass