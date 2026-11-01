"""
CompanyProfile — the single row holding this company's identity, branding,
region and payment configuration, edited by admins at
Settings → Company & Branding. Read it through apps.company.services.get_company().
"""
from django.core.validators import RegexValidator
from django.db import models

from utils.countries import COUNTRY_CHOICES, DEFAULT_COUNTRY, get_country
from utils.theme import DEFAULT_ACCENT, DEFAULT_PRIMARY

from .defaults import GENERIC_TERMS_ENGLISH

_hex_color = RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Pick a colour in #RRGGBB form.')


# M-Pesa (Daraja) configuration stored in CompanyProfile.mpesa, keyed by the
# settings/.env variable each one replaces. A non-blank value here wins; a
# blank one falls back to the environment, so existing deployments keep
# working until an admin moves a value into Settings.
#   (key, label, is_secret, group)
MPESA_FIELDS = [
    ('MPESA_ENV', 'Environment (sandbox or production)', False, 'general'),
    ('MPESA_RESULT_URL_BASE', 'Callback base URL (https://…)', False, 'general'),
    ('MPESA_CALLBACK_SECRET', 'Callback secret', True, 'general'),

    ('MPESA_SHORTCODE', 'Paybill number', False, 'paybill1'),
    ('MPESA_CONSUMER_KEY', 'Consumer key', True, 'paybill1'),
    ('MPESA_CONSUMER_SECRET', 'Consumer secret', True, 'paybill1'),
    ('MPESA_PASSKEY', 'STK passkey', True, 'paybill1'),
    ('MPESA_INITIATOR_NAME', 'Initiator name', False, 'paybill1'),
    ('MPESA_SECURITY_CREDENTIAL', 'Security credential', True, 'paybill1'),
    ('MPESA_C2B_CONFIRMATION_URL', 'C2B confirmation URL', False, 'paybill1'),
    ('MPESA_C2B_VALIDATION_URL', 'C2B validation URL', False, 'paybill1'),
    ('MPESA_STK_CALLBACK_URL', 'STK callback URL', False, 'paybill1'),

    ('MPESA_SHORTCODE_2', 'Paybill number', False, 'paybill2'),
    ('MPESA_CONSUMER_KEY_2', 'Consumer key', True, 'paybill2'),
    ('MPESA_CONSUMER_SECRET_2', 'Consumer secret', True, 'paybill2'),
    ('MPESA_PASSKEY_2', 'STK passkey', True, 'paybill2'),
    ('MPESA_INITIATOR_NAME_2', 'Initiator name', False, 'paybill2'),
    ('MPESA_SECURITY_CREDENTIAL_2', 'Security credential', True, 'paybill2'),
    ('MPESA_C2B_CONFIRMATION_URL_2', 'C2B confirmation URL', False, 'paybill2'),
    ('MPESA_C2B_VALIDATION_URL_2', 'C2B validation URL', False, 'paybill2'),
    ('MPESA_STK_CALLBACK_URL_2', 'STK callback URL', False, 'paybill2'),
    ('MPESA_BALANCE_RESULT_URL_2', 'Balance result URL', False, 'paybill2'),
    ('MPESA_BALANCE_TIMEOUT_URL_2', 'Balance timeout URL', False, 'paybill2'),
]
MPESA_KEYS = {key for key, _label, _secret, _group in MPESA_FIELDS}
MPESA_SECRET_KEYS = {key for key, _label, secret, _group in MPESA_FIELDS if secret}


class CompanyProfile(models.Model):
    LETTERHEAD_GENERATED = 'generated'
    LETTERHEAD_HEADER_FOOTER = 'header_footer'
    LETTERHEAD_FULL_PAGE = 'full_page'
    LETTERHEAD_CHOICES = [
        (LETTERHEAD_GENERATED, 'Automatic — built from the logo, details and colours'),
        (LETTERHEAD_HEADER_FOOTER, 'Uploaded header and footer images'),
        (LETTERHEAD_FULL_PAGE, 'Uploaded full-page letterhead image'),
    ]

    # ---- Identity ----
    legal_name = models.CharField('Legal name', max_length=200,
                                  help_text='Printed on agreements, receipts and reports')
    short_name = models.CharField('Short name', max_length=100,
                                  help_text='Used in signature lines and page titles, e.g. "Acme Motors Ltd"')
    display_name = models.CharField('Trading name', max_length=100, blank=True,
                                    help_text='The name customers know you by, shown on the public website, e.g. "Acme Motors"')
    app_name = models.CharField('App name', max_length=40, default='VMS',
                                help_text='Shown in the sidebar, browser tab and installed app')
    postal_address = models.CharField(max_length=255, blank=True)
    physical_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField('Phone number(s)', max_length=100, blank=True,
                             help_text='Separate several numbers with "/"')
    whatsapp = models.CharField('WhatsApp number', max_length=30, blank=True,
                                help_text='International format without "+", e.g. 254712345678')
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=200, blank=True)
    tax_pin = models.CharField('Tax PIN / TIN', max_length=50, blank=True)
    logo = models.ImageField(upload_to='company/', blank=True)
    # Social links shown in the website and app footers (left blank = hidden)
    facebook_url = models.URLField('Facebook page', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
    x_url = models.URLField('X (Twitter)', blank=True)
    tiktok_url = models.URLField('TikTok', blank=True)
    linkedin_url = models.URLField('LinkedIn', blank=True)
    youtube_url = models.URLField('YouTube', blank=True)

    # ---- Appearance ----
    primary_color = models.CharField(max_length=7, default=DEFAULT_PRIMARY, validators=[_hex_color])
    accent_color = models.CharField(max_length=7, default=DEFAULT_ACCENT, validators=[_hex_color])

    # ---- Region ----
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default=DEFAULT_COUNTRY)
    currency_code = models.CharField(max_length=3, default='KES')
    currency_symbol = models.CharField(max_length=10, default='KSh')
    currency_words = models.CharField('Currency in words', max_length=60, default='Kenya Shillings',
                                      help_text='Used for amounts written out in words, e.g. "Kenya Shillings"')
    locale = models.CharField(max_length=10, default='en-KE',
                              help_text='Number/date formatting in the browser, e.g. en-KE')
    time_zone = models.CharField(max_length=64, default='Africa/Nairobi')

    # ---- Documents ----
    letterhead_mode = models.CharField(max_length=20, choices=LETTERHEAD_CHOICES, default=LETTERHEAD_GENERATED)
    letterhead_header = models.ImageField(upload_to='company/letterhead/', blank=True,
                                          help_text='Wide image printed across the top of every page')
    letterhead_footer = models.ImageField(upload_to='company/letterhead/', blank=True,
                                          help_text='Wide image printed across the bottom of every page')
    letterhead_full_page = models.ImageField(upload_to='company/letterhead/', blank=True,
                                             help_text='One image covering the whole page (header, background and footer)')
    terms_primary_label = models.CharField('First language heading', max_length=40, default='ENGLISH')
    terms_primary = models.TextField('Agreement terms', default=GENERIC_TERMS_ENGLISH,
                                     help_text='One clause per line')
    terms_secondary_label = models.CharField('Second language heading', max_length=40, blank=True, default='KISWAHILI')
    terms_secondary = models.TextField('Agreement terms (second language)', blank=True,
                                       help_text='One clause per line, matching the first-language clauses. Leave blank for a single column.')
    seller_signature_line = models.CharField(max_length=120, blank=True,
                                             help_text='Printed under the seller signature, e.g. "For Acme Motors Ltd"')
    payment_note = models.CharField(max_length=200, blank=True,
                                    default='WE DO NOT ACCEPT THIRD PARTY PAYMENTS.',
                                    help_text='Printed under the paybill on agreements')
    email_subject_prefix = models.CharField(max_length=40, blank=True,
                                            help_text='Prepended to system email subjects, e.g. "[ACME] "')

    # ---- Payments ----
    mpesa = models.JSONField('M-Pesa settings', default=dict, blank=True)
    mpesa_use_server_settings = models.BooleanField(
        "Use the server's M-Pesa settings for blank fields", default=False,
        help_text='Only for the original deployment, whose M-Pesa keys live in the server .env. '
                  'New companies must enter their own.')
    channel_group_labels = models.JSONField(
        'Payment channel group names', default=dict, blank=True,
        help_text='Display names for the account groups, e.g. {"hoza": "Main accounts"}')

    version = models.PositiveIntegerField(default=1, editable=False,
                                          help_text='Bumped on every save; used to invalidate caches')
    updated_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_profile'
        verbose_name = 'Company Profile'
        verbose_name_plural = 'Company Profile'

    def __str__(self):
        return self.legal_name or 'Company profile'

    def save(self, *args, **kwargs):
        if self.pk:
            self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1, defaults={
            'legal_name': 'My Company', 'short_name': 'My Company',
        })
        return obj

    # ---- Convenience ----
    @property
    def country_preset(self):
        return get_country(self.country)

    @property
    def phones(self):
        return [p.strip() for p in (self.phone or '').split('/') if p.strip()]

    @property
    def primary_phone(self):
        phones = self.phones
        return phones[0] if phones else ''

    @property
    def primary_phone_tel(self):
        return ''.join(ch for ch in self.primary_phone if ch.isdigit() or ch == '+')

    @property
    def website_display(self):
        """Website without scheme or trailing slash, e.g. 'www.hozacars.com'."""
        site = (self.website or '').strip()
        for prefix in ('https://', 'http://'):
            if site.startswith(prefix):
                site = site[len(prefix):]
        return site.rstrip('/')

    SOCIAL_LINKS = [
        ('facebook_url', 'fab fa-facebook-f', 'Facebook'),
        ('instagram_url', 'fab fa-instagram', 'Instagram'),
        ('x_url', 'fab fa-twitter', 'X'),  # fa-x-twitter needs Font Awesome 6.4.2+; pages load 6.4.0
        ('tiktok_url', 'fab fa-tiktok', 'TikTok'),
        ('linkedin_url', 'fab fa-linkedin-in', 'LinkedIn'),
        ('youtube_url', 'fab fa-youtube', 'YouTube'),
    ]

    @property
    def social_links(self):
        """[(url, icon class, label)] for the links that are filled in."""
        return [(getattr(self, field), icon, label) for field, icon, label in self.SOCIAL_LINKS
                if getattr(self, field)]

    @property
    def public_name(self):
        return self.display_name or self.short_name or self.legal_name

    @property
    def seller_line(self):
        return self.seller_signature_line or f'For {self.short_name or self.legal_name}'

    @property
    def payroll_module(self):
        return self.country_preset.get('payroll_module', '')

    @property
    def currency(self):
        return self.currency_code

    def get_mpesa(self, key):
        """Decrypted stored M-Pesa value ('' when not set)."""
        from utils.crypto import decrypt
        value = (self.mpesa or {}).get(key, '')
        return decrypt(value) if key in MPESA_SECRET_KEYS else str(value or '')

    def set_mpesa(self, key, value):
        from utils.crypto import encrypt
        data = dict(self.mpesa or {})
        value = (value or '').strip()
        if not value:
            data.pop(key, None)
        else:
            data[key] = encrypt(value) if key in MPESA_SECRET_KEYS else value
        self.mpesa = data
