"""
Main URL Configuration for Vehicle Sales Management System
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
    path('', include('apps.core.urls', namespace='core')),
    
    # Vehicle Management
    # path('vehicles/', include('apps.vehicles.urls', namespace='vehicles')),
    
    # Client Management
    # path('clients/', include('apps.clients.urls', namespace='clients')),
    
    # Payment Management
    # path('payments/', include('apps.payments.urls', namespace='payments')),
    
    # Payroll Management
    # path('payroll/', include('apps.payroll.urls', namespace='payroll')),
    
    # Expense Tracking
    # path('expenses/', include('apps.expenses.urls', namespace='expenses')),
    
    # Repossessions
    # path('repossessions/', include('apps.repossessions.urls', namespace='repossessions')),
    
    # Auctions
    # path('auctions/', include('apps.auctions.urls', namespace='auctions')),
    
    # Insurance
    # path('insurance/', include('apps.insurance.urls', namespace='insurance')),
    
    # Notifications
    # path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    
    # Documents
    # path('documents/', include('apps.documents.urls', namespace='documents')),
    
    # Reports
    # path('reports/', include('apps.reports.urls', namespace='reports')),
    
    # Audit Logs
    # path('audit/', include('apps.audit.urls', namespace='audit')),
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

# Customize admin site
admin.site.site_header = "Vehicle Sales Management Admin"
admin.site.site_title = "Vehicle Sales Admin Portal"
admin.site.index_title = "Welcome to Vehicle Sales Management System"