"""
Platform background jobs.

Tasks sent from inside a company's request carry that company's schema
automatically (tenant-schemas-celery). Celery beat, however, runs on the
platform schema, so each periodic job is scheduled as run_for_all_companies,
which fans it out to every active company — see the wrap_periodic_tasks
command.
"""
import logging

from celery import current_app, shared_task

from .models import Company
from .provisioning import provision

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def provision_company(company_id):
    provision(company_id)


@shared_task(ignore_result=True)
def run_for_all_companies(task_name, args=None, kwargs=None):
    """Send `task_name` once per active company, each in that company's schema."""
    schemas = (Company.objects.filter(status=Company.STATUS_ACTIVE)
               .exclude(schema_name='public').values_list('schema_name', flat=True))
    for schema in schemas:
        current_app.send_task(task_name, args=args or [], kwargs=kwargs or {},
                              headers={'_schema_name': schema})
    logger.info('Fanned out %s to %d companies', task_name, len(schemas))
