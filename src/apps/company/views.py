"""
Settings → Company & Branding (administrators only).
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.audit.utils import log_audit
from apps.payments import channels
from apps.payments.models import Account
from utils.constants import UserRole
from utils.countries import COUNTRIES, PREFILL_FIELDS
from utils.currency import CURRENCY_NAMES
from utils.decorators import role_required

from .forms import PaymentChannelForm, CompanyProfileForm
from .services import get_company

TABS = [
    ('identity', 'Identity', 'fa-id-card'),
    ('appearance', 'Appearance', 'fa-palette'),
    ('region', 'Region', 'fa-globe-africa'),
    ('payments', 'Payments', 'fa-money-bill-wave'),
    ('documents', 'Documents', 'fa-file-signature'),
]


def _channel_rows():
    accounts = (Account.objects.exclude(payment_method_code__isnull=True)
                .exclude(payment_method_code='').order_by('display_order', 'category', 'name'))
    return [(account, PaymentChannelForm(instance=account, prefix=f'ch{account.pk}')) for account in accounts]


@login_required
@role_required(UserRole.ADMIN)
def company_settings(request):
    profile = get_company()
    tab = request.GET.get('tab') or request.POST.get('tab') or 'identity'

    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            changed = [f for f in form.changed_data if not f.startswith('clear_')]
            profile = form.save(commit=False)
            profile.updated_by = request.user
            profile.save()
            # Field names only — never log M-Pesa values
            log_audit(request.user, 'update', 'CompanyProfile',
                      f'Updated company settings: {", ".join(changed) or "no changes"}')
            messages.success(request, 'Company settings saved. Changes apply immediately.')
            return redirect(f"{request.path}?tab={tab}")
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = CompanyProfileForm(instance=profile)

    return render(request, 'company/settings.html', {
        'form': form,
        'profile': profile,
        'tabs': TABS,
        'active_tab': tab,
        'channel_rows': _channel_rows(),
        'new_channel_form': PaymentChannelForm(prefix='new', initial={'is_active': True, 'category': 'other'}),
        'currency_names': sorted(CURRENCY_NAMES.items()),
        'currency_names_json': json.dumps(CURRENCY_NAMES),
        'country_presets_json': json.dumps({
            code: {field: preset[key] for key, field in PREFILL_FIELDS.items()}
            for code, preset in COUNTRIES.items()
        }),
    })


@login_required
@role_required(UserRole.ADMIN)
@require_POST
def save_channel(request, pk=None):
    account = get_object_or_404(Account, pk=pk) if pk else None
    prefix = f'ch{pk}' if pk else 'new'
    form = PaymentChannelForm(request.POST, instance=account, prefix=prefix)
    if not form.is_valid():
        errors = '; '.join(f'{k}: {", ".join(v)}' for k, v in form.errors.items())
        messages.error(request, f'Payment channel not saved — {errors}')
        return redirect(f"{reverse('company:settings')}?tab=payments")

    channel = form.save(commit=False)
    if not channel.pk:
        channel.payment_method_code = channels.new_channel_code(channel.name, channel.category)
        channel.created_by = request.user
    channel.save()
    log_audit(request.user, 'create' if not pk else 'update', 'Account',
              f'{"Added" if not pk else "Updated"} payment channel "{channel.name}" ({channel.payment_method_code})')
    messages.success(request, f'Payment channel "{channel.name}" saved.')
    return redirect(f"{reverse('company:settings')}?tab=payments")


@login_required
@role_required(UserRole.ADMIN)
def preview_pdf(request, kind):
    """Render a sample document with the saved settings."""
    if kind == 'agreement':
        from apps.clients.models import ClientVehicle
        from apps.documents.sales_agreement_pdf import generate_sales_agreement_pdf

        client_vehicle = ClientVehicle.objects.select_related('client', 'vehicle').order_by('-pk').first()
        if client_vehicle is None:
            messages.info(request, 'Assign a vehicle to a client first — the agreement preview uses the latest sale.')
            return redirect(f"{reverse('company:settings')}?tab=documents")
        buffer = generate_sales_agreement_pdf(client_vehicle)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="sample_agreement.pdf"'
        return response

    from reportlab.platypus import Paragraph, Spacer

    from utils.report_kit import build_pdf_response, fmt_money, kpi_table, styled_table

    profile = get_company()

    def body(elements, styles):
        elements.append(kpi_table([
            ('Receipt No', 'RCT-SAMPLE-0001'),
            ('Amount Received', fmt_money(150000)),
            ('Payment Method', 'M-Pesa'),
        ]))
        elements.append(Spacer(1, 12))
        elements.append(styled_table([
            ['Date', 'Description', 'Amount'],
            ['01/01/2026', 'Deposit', fmt_money(100000)],
            ['01/02/2026', 'Instalment 1', fmt_money(50000)],
        ], align_right_from=2))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            'This is a sample receipt showing your letterhead, colours and currency.', styles['Normal']))

    response = build_pdf_response('sample_receipt.pdf', 'Sample Receipt',
                                  subtitle=profile.legal_name, build_body=body)
    response['Content-Disposition'] = 'inline; filename="sample_receipt.pdf"'
    return response
