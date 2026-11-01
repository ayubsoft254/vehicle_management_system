"""
Helpers that work whether or not multi-company mode (settings.MULTI_TENANT,
django-tenants) is switched on.

With MULTI_TENANT off there is one company and everything lives in the
"public" schema, exactly as before. With it on, each company has its own
PostgreSQL schema and "public" holds only the platform (company list,
control panel, platform-owner accounts).
"""
from django.conf import settings
from django.db import connection

PUBLIC_SCHEMA = 'public'


def multi_tenant():
    return getattr(settings, 'MULTI_TENANT', False)


def current_schema(conn=None):
    return getattr(conn or connection, 'schema_name', PUBLIC_SCHEMA) or PUBLIC_SCHEMA


def on_platform_schema(conn=None):
    """True while serving the platform (control panel) rather than a company."""
    return multi_tenant() and current_schema(conn) == PUBLIC_SCHEMA


def is_new_company_schema(schema_editor):
    """For data migrations: True when migrating a freshly provisioned company
    schema. Seed data that only made sense for the original single-company
    database (Hoza accounts, Hoza identity) is skipped there — provisioning
    seeds a new company from its country preset instead."""
    return current_schema(schema_editor.connection) != PUBLIC_SCHEMA
