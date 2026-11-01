"""
Celery configuration for Vehicle Management System
"""

import os

from decouple import config

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# In multi-company mode every task carries the schema of the company that
# queued it (tenant-schemas-celery), so .delay() from a company's request
# runs against that company's data.
if config('MULTI_TENANT', default=False, cast=bool):
    from tenant_schemas_celery.app import CeleryApp as Celery
else:
    from celery import Celery

# Create Celery app
app = Celery('vehicle_management_system')

# Load config from Django settings, with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
