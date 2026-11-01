"""
Country presets for the East African markets the system supports.

Choosing a country on the Company Settings page pre-fills the company
profile's currency, locale and time zone from here; the admin can then
override any of those values. The validation rules (phone, plate, tax and
national ID formats) and the payroll statutory module are always read from
the preset of the company's current country — see utils/validators.py and
apps/payroll/utils.py.
"""

COUNTRIES = {
    'KE': {
        'name': 'Kenya',
        'dial_code': '254',
        # National significant number (what follows the dial code / leading 0)
        'mobile_nsn_regex': r'[17]\d{8}',
        'phone_example': '+254712345678 or 0712345678',
        'currency_code': 'KES',
        'currency_symbol': 'KSh',
        'currency_words': 'Kenya Shillings',
        'locale': 'en-KE',
        'time_zone': 'Africa/Nairobi',
        'tax_id_label': 'KRA PIN',
        'tax_id_regex': r'[A-Z]\d{9}[A-Z]',
        'tax_id_example': 'A123456789X',
        'national_id_label': 'National ID',
        'national_id_regex': r'\d{7,8}',
        'national_id_example': '12345678',
        'plate_regex': r'K[A-Z]{2}\s?\d{3}[A-Z]',
        'plate_example': 'KAA 123A',
        'payroll_module': 'ke',
    },
    'UG': {
        'name': 'Uganda',
        'dial_code': '256',
        'mobile_nsn_regex': r'7\d{8}',
        'phone_example': '+256712345678 or 0712345678',
        'currency_code': 'UGX',
        'currency_symbol': 'USh',
        'currency_words': 'Uganda Shillings',
        'locale': 'en-UG',
        'time_zone': 'Africa/Kampala',
        'tax_id_label': 'TIN',
        'tax_id_regex': r'\d{10}',
        'tax_id_example': '1000123456',
        'national_id_label': 'NIN',
        'national_id_regex': r'[A-Z]{2}[A-Z0-9]{12}',
        'national_id_example': 'CM12345678ABCD',
        'plate_regex': r'U[A-Z]{2}\s?\d{3}[A-Z]',
        'plate_example': 'UBA 123A',
        'payroll_module': '',
    },
    'TZ': {
        'name': 'Tanzania',
        'dial_code': '255',
        'mobile_nsn_regex': r'[67]\d{8}',
        'phone_example': '+255712345678 or 0712345678',
        'currency_code': 'TZS',
        'currency_symbol': 'TSh',
        'currency_words': 'Tanzania Shillings',
        'locale': 'en-TZ',
        'time_zone': 'Africa/Dar_es_Salaam',
        'tax_id_label': 'TIN',
        'tax_id_regex': r'\d{3}-?\d{3}-?\d{3}',
        'tax_id_example': '123-456-789',
        'national_id_label': 'NIDA Number',
        'national_id_regex': r'\d{20}',
        'national_id_example': '19900101123450000123',
        'plate_regex': r'T\s?\d{3}\s?[A-Z]{3}',
        'plate_example': 'T 123 ABC',
        'payroll_module': '',
    },
    'RW': {
        'name': 'Rwanda',
        'dial_code': '250',
        'mobile_nsn_regex': r'7\d{8}',
        'phone_example': '+250781234567 or 0781234567',
        'currency_code': 'RWF',
        'currency_symbol': 'FRw',
        'currency_words': 'Rwandan Francs',
        'locale': 'en-RW',
        'time_zone': 'Africa/Kigali',
        'tax_id_label': 'TIN',
        'tax_id_regex': r'\d{9}',
        'tax_id_example': '123456789',
        'national_id_label': 'National ID',
        'national_id_regex': r'\d{16}',
        'national_id_example': '1199080012345678',
        'plate_regex': r'R[A-Z]{2}\s?\d{3}\s?[A-Z]',
        'plate_example': 'RAB 123 A',
        'payroll_module': '',
    },
}

DEFAULT_COUNTRY = 'KE'

COUNTRY_CHOICES = [(code, preset['name']) for code, preset in COUNTRIES.items()]

# Profile fields that choosing a country pre-fills (the admin may override).
PREFILL_FIELDS = {
    'currency_code': 'currency_code',
    'currency_symbol': 'currency_symbol',
    'currency_words': 'currency_words',
    'locale': 'locale',
    'time_zone': 'time_zone',
}


def get_country(code=None):
    """Preset for `code`, falling back to the default country."""
    return COUNTRIES.get((code or '').upper(), COUNTRIES[DEFAULT_COUNTRY])
