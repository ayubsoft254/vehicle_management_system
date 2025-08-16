from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')), 
    # path('', include('core.urls')),
    # path('vehicles/', include('vehicles.urls')),
    # path('clients/', include('clients.urls')),
    # path('payments/', include('payments.urls')),
    # path('payroll/', include('payroll.urls')),
    # path('expenses/', include('expenses.urls')),
    # path('auctions/', include('auctions.urls')),
    # path('insurance/', include('insurance.urls')),
    # path('documents/', include('documents.urls')),
    # path('reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)