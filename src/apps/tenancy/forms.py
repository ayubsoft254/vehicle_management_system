import re

from django import forms
from django.conf import settings
from django_tenants.utils import get_tenant_domain_model

from utils.countries import COUNTRY_CHOICES

from .models import Company

INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500'
RESERVED = {'www', 'admin', 'api', 'app', 'platform', 'public', 'mail', 'static', 'media', 'ftp', 'test'}
_SUBDOMAIN_RE = re.compile(r'^[a-z][a-z0-9-]{1,38}[a-z0-9]$')
_DOMAIN_RE = re.compile(r'^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


class NewCompanyForm(forms.Form):
    name = forms.CharField(label='Company name', max_length=200)
    subdomain = forms.CharField(
        max_length=40,
        help_text=f'Its web address will be <subdomain>.{settings.PLATFORM_DOMAIN}. '
                  'Lowercase letters, numbers and hyphens.')
    country = forms.ChoiceField(choices=COUNTRY_CHOICES)
    admin_email = forms.EmailField(label='First admin email',
                                   help_text='Receives a link to set a password and sign in.')
    admin_first_name = forms.CharField(label='Admin first name', max_length=150)
    admin_last_name = forms.CharField(label='Admin last name', max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', INPUT)

    def clean_subdomain(self):
        sub = self.cleaned_data['subdomain'].strip().lower()
        if not _SUBDOMAIN_RE.match(sub) or '--' in sub:
            raise forms.ValidationError('Use 3–40 lowercase letters, numbers and single hyphens, starting with a letter.')
        if sub in RESERVED:
            raise forms.ValidationError('That address is reserved.')
        if get_tenant_domain_model().objects.filter(domain=f'{sub}.{settings.PLATFORM_DOMAIN}').exists():
            raise forms.ValidationError('That address is already taken.')
        if Company.objects.filter(schema_name=schema_for(sub)).exists():
            raise forms.ValidationError('That address is already taken.')
        return sub


def schema_for(subdomain):
    return subdomain.replace('-', '_')


class DomainForm(forms.Form):
    domain = forms.CharField(
        label='Custom web address', max_length=253,
        help_text='e.g. portal.acmemotors.co.ke — then point its DNS at this server.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['domain'].widget.attrs.setdefault('class', INPUT)

    def clean_domain(self):
        domain = self.cleaned_data['domain'].strip().lower().rstrip('.')
        for prefix in ('https://', 'http://'):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.split('/')[0]
        if not _DOMAIN_RE.match(domain):
            raise forms.ValidationError('Enter a domain name like portal.example.com.')
        if domain == settings.PLATFORM_DOMAIN:
            raise forms.ValidationError('That is the platform\'s own address.')
        if get_tenant_domain_model().objects.filter(domain=domain).exists():
            raise forms.ValidationError('That address is already in use.')
        return domain
