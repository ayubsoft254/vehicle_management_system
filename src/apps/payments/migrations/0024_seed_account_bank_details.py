"""
Payment channels became data: keep the six legacy accounts in their old
menu order, and move the proforma bank details that were hardcoded in
ProformaInvoice.COMPANY_ACCOUNTS onto the matching accounts.
"""
from django.db import migrations

LEGACY_ORDER = ['equity_hoza', 'dib_hoza', 'coop_hoza', 'kcb_ke', 'absa_ke', 'equity_ke']


def seed(apps, schema_editor):
    from utils.tenancy import is_new_company_schema
    if is_new_company_schema(schema_editor):
        return  # a new company's schema: provisioning seeds its own data
    from apps.company.defaults import HOZA_BANK_ACCOUNTS

    Account = apps.get_model('payments', 'Account')
    for position, code in enumerate(LEGACY_ORDER, start=1):
        Account.objects.filter(payment_method_code=code).update(display_order=position)

    for details in HOZA_BANK_ACCOUNTS.values():
        account = Account.objects.filter(payment_method_code=details['payment_method_code']).first()
        if account is None or account.account_number:
            continue
        account.bank_name = details['bank']
        account.branch = details['branch']
        account.account_holder_name = details['account_name']
        account.account_number = details['account_number']
        account.show_on_proforma = True
        account.save(update_fields=['bank_name', 'branch', 'account_holder_name',
                                    'account_number', 'show_on_proforma'])


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0023_alter_account_options_account_account_holder_name_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
