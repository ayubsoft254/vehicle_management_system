"""
The platform's list of companies (django-tenants tenants) and their web
addresses. These live in the shared "public" schema; each Company's own
data lives in its PostgreSQL schema (Company.schema_name).

Named Company rather than the django-tenants convention "Client" to avoid
confusion with apps.clients.Client (a customer).
"""
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

from utils.countries import COUNTRY_CHOICES, DEFAULT_COUNTRY


class Company(TenantMixin):
    STATUS_PROVISIONING = 'provisioning'
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PROVISIONING, 'Setting up'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
        (STATUS_FAILED, 'Setup failed'),
    ]

    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROVISIONING)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default=DEFAULT_COUNTRY)
    admin_email = models.EmailField('First admin email', blank=True)
    admin_first_name = models.CharField(max_length=150, blank=True)
    admin_last_name = models.CharField(max_length=150, blank=True)
    progress = models.CharField(max_length=200, blank=True, help_text='Current provisioning step')
    error = models.TextField(blank=True)
    created_by = models.CharField(max_length=254, blank=True, help_text='Platform owner who created it')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    # Schemas are created by the provisioning task (with progress), not
    # synchronously inside save(); never dropped automatically.
    auto_create_schema = False
    auto_drop_schema = False

    class Meta:
        db_table = 'tenancy_company'
        ordering = ['name']
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name

    @property
    def is_platform(self):
        return self.schema_name == 'public'

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first() or self.domains.first()


class Domain(DomainMixin):
    """A web address that serves one company (subdomain or custom domain)."""

    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenancy_domain'
        ordering = ['-is_primary', 'domain']

    def __str__(self):
        return self.domain
