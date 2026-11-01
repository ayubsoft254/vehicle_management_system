import zoneinfo

from django import forms
from django.conf import settings

from apps.payments.channels import DEFAULT_GROUP_LABELS, GROUP_CODES, group_choices
from apps.payments.models import Account

from .models import MPESA_FIELDS, CompanyProfile
from .services import company_base_url

INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500'

IDENTITY_FIELDS = ['legal_name', 'short_name', 'display_name', 'app_name', 'postal_address', 'physical_address', 'city',
                   'phone', 'whatsapp', 'email', 'website', 'tax_pin', 'logo']
SOCIAL_FIELDS = ['facebook_url', 'instagram_url', 'x_url', 'tiktok_url', 'linkedin_url', 'youtube_url']
APPEARANCE_FIELDS = ['primary_color', 'accent_color']
REGION_FIELDS = ['country', 'currency_code', 'currency_symbol', 'currency_words', 'locale', 'time_zone']
DOCUMENT_FIELDS = ['letterhead_mode', 'letterhead_header', 'letterhead_footer', 'letterhead_full_page',
                   'terms_primary_label', 'terms_primary', 'terms_secondary_label', 'terms_secondary',
                   'seller_signature_line', 'payment_note', 'email_subject_prefix']

MPESA_GROUPS = [
    ('general', 'General'),
    ('paybill1', 'Paybill 1 (primary)'),
    ('paybill2', 'Paybill 2 (optional)'),
]


def _time_zone_choices():
    zones = sorted(z for z in zoneinfo.available_timezones() if z.startswith('Africa/'))
    return [(z, z.replace('_', ' ')) for z in zones]


class CompanyProfileForm(forms.ModelForm):
    time_zone = forms.ChoiceField(choices=_time_zone_choices)

    class Meta:
        model = CompanyProfile
        fields = IDENTITY_FIELDS + SOCIAL_FIELDS + APPEARANCE_FIELDS + REGION_FIELDS + DOCUMENT_FIELDS
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
            # Rendered as radio buttons in the template (radio.tag); the
            # default <select> would submit nothing and fail every save.
            'letterhead_mode': forms.RadioSelect,
            'terms_primary': forms.Textarea(attrs={'rows': 10}),
            'terms_secondary': forms.Textarea(attrs={'rows': 10}),
            'logo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'letterhead_header': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'letterhead_footer': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'letterhead_full_page': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep a zone saved before this list existed selectable
        current = self.instance.time_zone
        if current and current not in dict(self.fields['time_zone'].choices):
            self.fields['time_zone'].choices = [(current, current)] + list(self.fields['time_zone'].choices)

        # Falling back to the server's .env can only be switched off here,
        # never on — on a shared server that .env belongs to another company.
        if self.instance.mpesa_use_server_settings:
            self.fields['mpesa_use_server_settings'] = forms.BooleanField(
                label="Use the server's M-Pesa settings for blank fields", required=False, initial=True,
                help_text='Untick once all your M-Pesa details are entered above.')

        # Payment channel group names
        labels = self.instance.channel_group_labels or {}
        for code in GROUP_CODES:
            self.fields[f'group_label_{code}'] = forms.CharField(
                label=f'Group "{DEFAULT_GROUP_LABELS[code]}"', max_length=40, required=False,
                initial=labels.get(code, ''), help_text=f'Default: {DEFAULT_GROUP_LABELS[code]}')

        # M-Pesa — secrets are never sent back to the browser
        for key, label, secret, _group in MPESA_FIELDS:
            if secret:
                self.fields[key] = forms.CharField(
                    label=label, required=False, strip=True,
                    widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}))
                self.fields[f'clear_{key}'] = forms.BooleanField(label='Clear', required=False)
            else:
                server_value = str(getattr(settings, key, '') or '') if self.instance.mpesa_use_server_settings else ''
                placeholder = f'Server value: {server_value}' if server_value else ''
                if key == 'MPESA_RESULT_URL_BASE' and not server_value:
                    default_base = company_base_url()
                    placeholder = f'Default: {default_base}' if default_base else 'https://your-address'
                self.fields[key] = forms.CharField(
                    label=label, required=False, initial=self.instance.get_mpesa(key),
                    widget=forms.TextInput(attrs={'placeholder': placeholder}))

        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.ClearableFileInput, forms.RadioSelect)):
                continue
            if widget.attrs.get('type') == 'color':
                widget.attrs['class'] = 'h-10 w-16 border border-gray-300 rounded cursor-pointer'
                continue
            widget.attrs.setdefault('class', INPUT)

    def clean_currency_code(self):
        code = (self.cleaned_data.get('currency_code') or '').strip().upper()
        if not (len(code) == 3 and code.isalpha() and code.isascii()):
            raise forms.ValidationError('Use the 3-letter ISO currency code, e.g. KES, UGX, TZS, RWF.')
        return code

    def mpesa_rows(self):
        """[(group label, [(bound field, clear field or None, is_set)])] for the template."""
        rows = []
        for group, group_label in MPESA_GROUPS:
            items = []
            for key, _label, secret, g in MPESA_FIELDS:
                if g != group:
                    continue
                items.append((self[key], self[f'clear_{key}'] if secret else None,
                              bool(self.instance.get_mpesa(key))))
            rows.append((group_label, items))
        return rows

    def section(self, names):
        return [self[name] for name in names]

    def identity_fields(self):
        return self.section([f for f in IDENTITY_FIELDS if f != 'logo'])

    def social_fields(self):
        return self.section(SOCIAL_FIELDS)

    def region_fields(self):
        return self.section([f for f in REGION_FIELDS if f != 'country'])

    def letterhead_upload_fields(self):
        return self.section(['letterhead_header', 'letterhead_footer', 'letterhead_full_page'])

    def agreement_fields(self):
        return self.section(['terms_primary_label', 'terms_secondary_label', 'terms_primary', 'terms_secondary',
                             'seller_signature_line', 'payment_note', 'email_subject_prefix'])

    def group_label_fields(self):
        return [self[f'group_label_{code}'] for code in GROUP_CODES]

    def save(self, commit=True):
        profile = super().save(commit=False)
        if 'mpesa_use_server_settings' in self.fields:
            profile.mpesa_use_server_settings = bool(self.cleaned_data.get('mpesa_use_server_settings'))
        profile.channel_group_labels = {
            code: self.cleaned_data[f'group_label_{code}'].strip()
            for code in GROUP_CODES if self.cleaned_data.get(f'group_label_{code}', '').strip()
        }
        for key, _label, secret, _group in MPESA_FIELDS:
            value = self.cleaned_data.get(key, '')
            if secret:
                if self.cleaned_data.get(f'clear_{key}'):
                    profile.set_mpesa(key, '')
                elif value:
                    profile.set_mpesa(key, value)
            else:
                profile.set_mpesa(key, value)
        if commit:
            profile.save()
        return profile


class PaymentChannelForm(forms.ModelForm):
    """Add or edit a payment channel (a finance Account with a payment code)."""

    category = forms.ChoiceField(label='Group', choices=group_choices)

    class Meta:
        model = Account
        fields = ['name', 'category', 'account_type', 'bank_name', 'branch', 'account_holder_name',
                  'account_number', 'show_on_proforma', 'is_active', 'display_order']
        labels = {'name': 'Name shown to cashiers', 'is_active': 'Active'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', INPUT)
