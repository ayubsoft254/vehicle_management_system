"""
Platform control panel (served on PLATFORM_DOMAIN, platform owners only) and
the support sign-in endpoint it uses on company domains.
"""
import logging
import threading
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core import signing
from django.db import close_old_connections, connection, transaction
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_tenants.utils import schema_context

from apps.audit.utils import log_audit

from .forms import DomainForm, NewCompanyForm, schema_for
from .models import Company, Domain
from .provisioning import admin_login_link, company_url, provision

logger = logging.getLogger(__name__)

SUPPORT_SALT = 'tenancy.support-login'
SUPPORT_MAX_AGE = 120  # seconds


def platform_owner_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('platform:login')}?next={request.path}")
        if not request.user.is_superuser:
            return HttpResponseForbidden('Platform owners only.')
        return view(request, *args, **kwargs)
    return wrapper


class PlatformLoginView(LoginView):
    template_name = 'tenancy/login.html'
    redirect_authenticated_user = True


class PlatformLogoutView(LogoutView):
    next_page = 'platform:login'


def _start_provisioning(company):
    """Queue the setup job; without a reachable Celery broker (e.g. local
    development) run it in a background thread instead."""
    from .tasks import provision_company
    try:
        provision_company.delay(company.pk)
        return
    except Exception:
        logger.warning('Celery unavailable — provisioning %s in a thread', company.schema_name)

    def run():
        close_old_connections()
        try:
            provision(company.pk)
        except Exception:
            pass  # recorded on the company as status=failed
        finally:
            connection.close()

    threading.Thread(target=run, daemon=True, name=f'provision-{company.schema_name}').start()


def _user_count(company):
    if company.status != Company.STATUS_ACTIVE:
        return None
    from apps.authentication.models import User
    try:
        with schema_context(company.schema_name):
            return User.objects.filter(is_active=True).count()
    except Exception:
        return None


@platform_owner_required
def company_list(request):
    companies = list(Company.objects.exclude(schema_name='public').prefetch_related('domains'))
    for company in companies:
        company.user_count = _user_count(company)
    return render(request, 'tenancy/company_list.html', {'companies': companies})


@platform_owner_required
def company_create(request):
    form = NewCompanyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            company = Company.objects.create(
                name=data['name'], schema_name=schema_for(data['subdomain']), country=data['country'],
                admin_email=data['admin_email'], admin_first_name=data['admin_first_name'],
                admin_last_name=data['admin_last_name'], created_by=request.user.email,
                progress='Queued',
            )
            Domain.objects.create(tenant=company, domain=f"{data['subdomain']}.{settings.PLATFORM_DOMAIN}",
                                  is_primary=True)
        log_audit(request.user, 'create', 'Company', f'Created company {company.name} ({company.schema_name})')
        transaction.on_commit(lambda: _start_provisioning(company))
        return redirect('platform:company_detail', pk=company.pk)
    return render(request, 'tenancy/company_form.html', {'form': form, 'platform_domain': settings.PLATFORM_DOMAIN})


@platform_owner_required
def company_detail(request, pk):
    company = get_object_or_404(Company.objects.exclude(schema_name='public'), pk=pk)
    return render(request, 'tenancy/company_detail.html', {
        'company': company,
        'domain_form': DomainForm(),
        'company_url': company_url(company),
        'platform_domain': settings.PLATFORM_DOMAIN,
    })


@platform_owner_required
def company_status(request, pk):
    company = get_object_or_404(Company, pk=pk)
    return JsonResponse({'status': company.status, 'status_label': company.get_status_display(),
                         'progress': company.progress, 'failed': company.status == Company.STATUS_FAILED})


def _company_action(view):
    @platform_owner_required
    @require_POST
    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        company = get_object_or_404(Company.objects.exclude(schema_name='public'), pk=pk)
        view(request, company, *args, **kwargs)
        return redirect('platform:company_detail', pk=company.pk)
    return wrapper


@_company_action
def company_suspend(request, company):
    company.status = Company.STATUS_SUSPENDED
    company.save(update_fields=['status', 'updated_on'])
    log_audit(request.user, 'update', 'Company', f'Suspended {company.name}')
    messages.success(request, f'{company.name} is suspended. Its users see a "temporarily unavailable" page; '
                              'M-Pesa payments are still recorded.')


@_company_action
def company_reactivate(request, company):
    if company.status != Company.STATUS_SUSPENDED:
        messages.error(request, 'Only a suspended company can be reactivated.')
        return
    company.status = Company.STATUS_ACTIVE
    company.save(update_fields=['status', 'updated_on'])
    log_audit(request.user, 'update', 'Company', f'Reactivated {company.name}')
    messages.success(request, f'{company.name} is active again.')


@_company_action
def company_retry(request, company):
    if company.status not in (Company.STATUS_FAILED, Company.STATUS_PROVISIONING):
        messages.error(request, 'This company is already set up.')
        return
    company.progress = 'Queued'
    company.save(update_fields=['progress', 'updated_on'])
    _start_provisioning(company)
    log_audit(request.user, 'action', 'Company', f'Retried setup of {company.name}')


@_company_action
def company_resend_login(request, company):
    from .provisioning import _email_admin
    try:
        _email_admin(company, admin_login_link(company))
        messages.success(request, f'Sent a new sign-in link to {company.admin_email}.')
    except Exception as exc:
        messages.error(request, f'Could not send the email: {exc}')


@_company_action
def domain_add(request, company):
    form = DomainForm(request.POST)
    if not form.is_valid():
        messages.error(request, '; '.join(form.errors['domain']))
        return
    Domain.objects.create(tenant=company, domain=form.cleaned_data['domain'], is_primary=False)
    log_audit(request.user, 'create', 'Domain', f'Added {form.cleaned_data["domain"]} to {company.name}')
    messages.success(request, f'Added {form.cleaned_data["domain"]}. Point its DNS at this server, '
                              'then issue its certificate (see the runbook).')


@_company_action
def domain_remove(request, company, domain_id):
    domain = get_object_or_404(Domain, pk=domain_id, tenant=company)
    if domain.is_primary:
        messages.error(request, 'Make another address primary before removing this one.')
        return
    domain.delete()
    log_audit(request.user, 'delete', 'Domain', f'Removed {domain.domain} from {company.name}')
    messages.success(request, f'Removed {domain.domain}.')


@_company_action
def domain_make_primary(request, company, domain_id):
    domain = get_object_or_404(Domain, pk=domain_id, tenant=company)
    with transaction.atomic():
        company.domains.update(is_primary=False)
        domain.is_primary = True
        domain.save(update_fields=['is_primary'])
    messages.success(request, f'{domain.domain} is now the main address.')


@platform_owner_required
@require_POST
def company_open(request, pk):
    """Sign in to a company as its admin, for support. Leaves an audit trail
    on the platform and in the company's own audit log."""
    company = get_object_or_404(Company.objects.exclude(schema_name='public'), pk=pk,
                                status=Company.STATUS_ACTIVE)
    token = signing.dumps({'schema': company.schema_name, 'by': request.user.email}, salt=SUPPORT_SALT)
    log_audit(request.user, 'action', 'Company', f'Opened {company.name} as support')
    # The sign-in route lives in the company URLconf, not this platform one
    return redirect(company_url(company, reverse('tenancy_support_login', args=[token], urlconf='config.urls')))


def support_login(request, token):
    """Company-side end of company_open (mounted in the company URLconf)."""
    try:
        data = signing.loads(token, salt=SUPPORT_SALT, max_age=SUPPORT_MAX_AGE)
    except signing.BadSignature:
        raise Http404
    if data.get('schema') != connection.schema_name:
        raise Http404

    from apps.authentication.models import User
    from utils.constants import UserRole
    admin = (User.objects.filter(is_active=True, role=UserRole.ADMIN).order_by('date_joined').first()
             or User.objects.filter(is_active=True, is_superuser=True).first())
    if admin is None:
        raise Http404
    login(request, admin, backend='django.contrib.auth.backends.ModelBackend')
    log_audit(admin, 'login', 'User', f'Platform support sign-in by {data.get("by")}')
    messages.info(request, f'Signed in as {admin.email} for platform support ({data.get("by")}).')
    return redirect('/dashboard/')
