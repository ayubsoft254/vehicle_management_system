"""
Template tags for the finance app.
"""
from django import template

from apps.finance.models import FinancialAccount

register = template.Library()


@register.simple_tag
def active_finance_accounts():
    """List active financial accounts, for populating "receiving/paying account" selects."""
    return FinancialAccount.objects.filter(status='active').order_by('name')
