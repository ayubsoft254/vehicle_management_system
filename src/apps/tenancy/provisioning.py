"""
Setting up a new company: create its schema (which runs every migration),
then seed it so its first admin can log in and start working without anyone
touching the server.
"""
import logging
import traceback

from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.db import transaction
from django_tenants.utils import schema_context

from apps.company.defaults import GENERIC_TERMS_ENGLISH
from utils.countries import PREFILL_FIELDS, get_country

from .models import Company

logger = logging.getLogger(__name__)


def company_url(company, path='/'):
    domain = company.primary_domain
    host = domain.domain if domain else settings.PLATFORM_DOMAIN
    return f'{settings.PLATFORM_SCHEME}://{host}{path}'


def _step(company, text):
    company.progress = text
    company.save(update_fields=['progress', 'updated_on'])


def _seed_profile(company):
    from apps.company.models import CompanyProfile

    preset = get_country(company.country)
    profile = CompanyProfile.get_solo()
    profile.legal_name = profile.short_name = profile.display_name = company.name
    profile.app_name = company.name[:40]
    profile.email = company.admin_email
    profile.country = company.country
    for preset_key, field in PREFILL_FIELDS.items():
        setattr(profile, field, preset[preset_key])
    profile.terms_primary = GENERIC_TERMS_ENGLISH
    profile.terms_secondary = ''
    profile.terms_secondary_label = ''
    profile.seller_signature_line = ''
    profile.email_subject_prefix = ''
    profile.letterhead_mode = CompanyProfile.LETTERHEAD_GENERATED
    profile.mpesa_use_server_settings = False
    profile.channel_group_labels = {'hoza': 'Bank accounts', 'ke': 'Other accounts'}
    # Viewing/export currencies: dollar, euro and the East African neighbours
    profile.other_currencies = [{'code': code, 'rate': ''} for code in ('USD', 'EUR', 'KES', 'UGX', 'TZS', 'RWF')
                                if code != profile.currency_code]
    profile.save()


def _seed_channels():
    from apps.payments import channels
    from apps.payments.models import Account

    if Account.objects.exists():
        return
    Account.objects.create(
        name='Main Bank Account', category='hoza', account_type='bank',
        payment_method_code=channels.new_channel_code('Main Bank Account', 'hoza'),
        show_on_proforma=True, display_order=1,
        notes='Created when the company was set up — add the bank details in Settings → Company & Branding.',
    )


def _create_admin(company):
    """First admin, with no password yet — they set one from the emailed link."""
    from allauth.account.forms import default_token_generator
    from allauth.account.models import EmailAddress
    from allauth.account.utils import user_pk_to_url_str
    from django.urls import reverse

    from apps.authentication.models import User
    from utils.constants import UserRole

    user = User.objects.filter(email__iexact=company.admin_email).first()
    if user is None:
        user = User.objects.create_user(
            email=company.admin_email, password=None,
            first_name=company.admin_first_name or 'Admin',
            last_name=company.admin_last_name or '',
            role=UserRole.ADMIN, is_staff=True,
        )
    EmailAddress.objects.get_or_create(user=user, email=user.email,
                                       defaults={'verified': True, 'primary': True})
    # Company-side route: name it explicitly, since this also runs from the
    # platform control panel ("Re-send sign-in link"), whose URLconf lacks it.
    path = reverse('account_reset_password_from_key', urlconf='config.urls', kwargs={
        'uidb36': user_pk_to_url_str(user), 'key': default_token_generator.make_token(user),
    })
    return user, company_url(company, path)


def _email_admin(company, link):
    send_mail(
        subject=f'Your {company.name} account is ready',
        message=(
            f'Hello {company.admin_first_name or ""},\n\n'
            f'{company.name} has been set up on {settings.PLATFORM_NAME}.\n\n'
            f'Set your password and sign in here:\n{link}\n\n'
            f'Your web address: {company_url(company)}\n\n'
            'After signing in, open Settings → Company & Branding to add your logo, '
            'colours, contact details, bank accounts and M-Pesa paybill.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[company.admin_email],
        fail_silently=False,
    )


def provision(company_id):
    """Create and seed a company's schema. Safe to re-run after a failure."""
    company = Company.objects.get(pk=company_id)
    if company.is_platform:
        return
    try:
        company.status, company.error = Company.STATUS_PROVISIONING, ''
        company.save(update_fields=['status', 'error', 'updated_on'])

        _step(company, 'Creating the company database (this takes a minute or two)')
        company.create_schema(check_if_exists=True, verbosity=0)

        with schema_context(company.schema_name):
            _step(company, 'Setting up roles and permissions')
            call_command('init_permissions', verbosity=0)

            _step(company, 'Applying country settings and payment channels')
            with transaction.atomic():
                _seed_profile(company)
                _seed_channels()

            _step(company, 'Creating the first admin')
            with transaction.atomic():
                _user, link = _create_admin(company)

        _step(company, 'Emailing the admin a login link')
        try:
            _email_admin(company, link)
        except Exception as exc:  # setup is complete; the link can be re-sent
            logger.exception('Could not email admin for %s', company.schema_name)
            company.error = f'Company is ready but the login email failed: {exc}'

        company.status = Company.STATUS_ACTIVE
        company.progress = 'Ready'
        company.save(update_fields=['status', 'progress', 'error', 'updated_on'])
        return link
    except Exception:
        logger.exception('Provisioning failed for %s', company.schema_name)
        company.status = Company.STATUS_FAILED
        company.error = traceback.format_exc()[-4000:]
        company.save(update_fields=['status', 'error', 'updated_on'])
        raise


def admin_login_link(company):
    """A fresh set-password link for the company's first admin."""
    with schema_context(company.schema_name):
        _user, link = _create_admin(company)
    return link
