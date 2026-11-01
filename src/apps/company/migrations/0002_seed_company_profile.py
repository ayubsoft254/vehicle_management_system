"""
Create the first CompanyProfile from what was configured before Company
Settings existed — settings.COMPANY_* (from .env), the Hoza literals that
were hardcoded in the sales agreement and email prefix, and the full-page
letterhead image — so documents and pages look exactly as they did.
"""
import os

from django.conf import settings
from django.db import migrations

HOZA_DEFAULT_NAME = 'HOZA INVESTMENT (K) LIMITED'


def seed(apps, schema_editor):
    from utils.tenancy import is_new_company_schema
    if is_new_company_schema(schema_editor):
        return  # a new company's schema: provisioning seeds its own data
    from apps.company.defaults import HOZA_TERMS_ENGLISH, HOZA_TERMS_SWAHILI

    CompanyProfile = apps.get_model('company', 'CompanyProfile')
    if CompanyProfile.objects.exists():
        return

    name = getattr(settings, 'COMPANY_NAME', '') or HOZA_DEFAULT_NAME
    website = getattr(settings, 'COMPANY_WEBSITE', '') or ''
    # Hoza deployments may carry a placeholder .env (e.g. "Hoza Cars"), but
    # their documents always printed the identity below — keep it exactly.
    is_hoza = 'HOZA' in name.upper() or 'hozacars' in website.lower()

    if is_hoza:
        identity = dict(
            legal_name=HOZA_DEFAULT_NAME,
            short_name='HOZA INVESTMENT (K) LTD',
            display_name='Hoza Investments',
            app_name='Hoza',
            postal_address='P.O BOX 43074-80100 MOMBASA, Kenya',
            physical_address='Mombasa - Kenya',
            city='Mombasa',
            phone='+254700170447 / +254784170447',
            whatsapp='254784170447',
            email='hozainvltd@gmail.com',
            website='https://www.hozacars.com/',
            tax_pin=getattr(settings, 'COMPANY_PIN', '') or 'PO51811452A',
        )
    else:
        identity = dict(
            legal_name=name,
            short_name=name,
            display_name=name,
            app_name='VMS',
            postal_address=getattr(settings, 'COMPANY_ADDRESS', ''),
            phone=getattr(settings, 'COMPANY_PHONE', ''),
            email=getattr(settings, 'COMPANY_EMAIL', ''),
            website=website,
            tax_pin=getattr(settings, 'COMPANY_PIN', ''),
        )

    profile = CompanyProfile(
        pk=1,
        **identity,
        # Every deployment printed these Hoza terms until now, so keep them;
        # admins replace them from Settings.
        terms_primary=HOZA_TERMS_ENGLISH,
        terms_secondary=HOZA_TERMS_SWAHILI,
        seller_signature_line='For HOZA INVESTMENT (K) LTD',
        email_subject_prefix=getattr(settings, 'ACCOUNT_EMAIL_SUBJECT_PREFIX', '') or '[HOZACARS] ',
        letterhead_mode='generated',
        # This deployment's M-Pesa keys are in .env — keep using them
        mpesa_use_server_settings=True,
    )

    letterhead = os.path.join(settings.BASE_DIR, 'static', 'img', 'letterhead.jpg')
    if os.path.exists(letterhead):
        from django.core.files import File
        with open(letterhead, 'rb') as fh:
            profile.letterhead_full_page.save('letterhead.jpg', File(fh), save=False)
        profile.letterhead_mode = 'full_page'

    profile.save()


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
