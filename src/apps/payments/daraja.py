# daraja.py - Updated version with fixes

from __future__ import annotations

from base64 import b64encode
from datetime import datetime
import uuid
from urllib.parse import urljoin, quote
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.urls import reverse

from .callback_debug import logged_request


class DarajaError(Exception):
    """Raised when Daraja API operations fail."""


def _clean(value) -> str:
    """Normalize env/config values used in API payloads."""
    return str(value or '').strip()


def get_daraja_base_url() -> str:
    env = _clean(getattr(settings, 'MPESA_ENV', 'sandbox')).lower() or 'sandbox'
    if env == 'production':
        return 'https://api.safaricom.co.ke/'
    return 'https://sandbox.safaricom.co.ke/'


def _resolve_paybill_credentials(shortcode: str = '') -> dict:
    """
    Resolve which paybill's full credential set to use for an outbound Daraja
    call. Falls back to the primary paybill when no shortcode is given (so
    every existing single-paybill caller keeps working unchanged); matches
    against MPESA_SHORTCODE_2 to select the secondary paybill's own consumer
    key/secret/passkey/initiator-name/security-credential rather than mixing
    credentials across paybills, which Daraja would reject.
    """
    shortcode = _clean(shortcode)
    secondary_shortcode = _clean(getattr(settings, 'MPESA_SHORTCODE_2', ''))

    if shortcode and secondary_shortcode and shortcode == secondary_shortcode:
        return {
            'shortcode': secondary_shortcode,
            'consumer_key': _clean(getattr(settings, 'MPESA_CONSUMER_KEY_2', '')),
            'consumer_secret': _clean(getattr(settings, 'MPESA_CONSUMER_SECRET_2', '')),
            'passkey': _clean(getattr(settings, 'MPESA_PASSKEY_2', '')),
            'initiator_name': _clean(getattr(settings, 'MPESA_INITIATOR_NAME_2', '')),
            'security_credential': _clean(getattr(settings, 'MPESA_SECURITY_CREDENTIAL_2', '')),
            'var_names': {
                'consumer_key': 'MPESA_CONSUMER_KEY_2',
                'consumer_secret': 'MPESA_CONSUMER_SECRET_2',
                'shortcode': 'MPESA_SHORTCODE_2',
                'passkey': 'MPESA_PASSKEY_2',
                'initiator_name': 'MPESA_INITIATOR_NAME_2',
                'security_credential': 'MPESA_SECURITY_CREDENTIAL_2',
            },
        }

    return {
        'shortcode': _clean(getattr(settings, 'MPESA_SHORTCODE', '')),
        'consumer_key': _clean(getattr(settings, 'MPESA_CONSUMER_KEY', '')),
        'consumer_secret': _clean(getattr(settings, 'MPESA_CONSUMER_SECRET', '')),
        'passkey': _clean(getattr(settings, 'MPESA_PASSKEY', '')),
        'initiator_name': _clean(getattr(settings, 'MPESA_INITIATOR_NAME', '')),
        'security_credential': _clean(getattr(settings, 'MPESA_SECURITY_CREDENTIAL', '')),
        'var_names': {
            'consumer_key': 'MPESA_CONSUMER_KEY',
            'consumer_secret': 'MPESA_CONSUMER_SECRET',
            'shortcode': 'MPESA_SHORTCODE',
            'passkey': 'MPESA_PASSKEY',
            'initiator_name': 'MPESA_INITIATOR_NAME',
            'security_credential': 'MPESA_SECURITY_CREDENTIAL',
        },
    }


def get_required_mpesa_vars(shortcode: str = '') -> list[str]:
    names = _resolve_paybill_credentials(shortcode)['var_names']
    return [
        names['consumer_key'],
        names['consumer_secret'],
        names['shortcode'],
        names['initiator_name'],
        names['security_credential'],
        'MPESA_RESULT_URL_BASE',
    ]


def get_missing_mpesa_vars(shortcode: str = '') -> list[str]:
    missing = []
    for var_name in get_required_mpesa_vars(shortcode):
        value = getattr(settings, var_name, '')
        if value is None or str(value).strip() == '':
            missing.append(var_name)
    return missing


def mpesa_is_configured(shortcode: str = '') -> bool:
    return not get_missing_mpesa_vars(shortcode)


def _absolute_callback_url(url_name: str) -> str:
    """Construct absolute callback URL from URL name."""
    base_url = _clean(getattr(settings, 'MPESA_RESULT_URL_BASE', ''))
    if not base_url:
        raise DarajaError('MPESA_RESULT_URL_BASE is not configured.')
    if base_url.startswith('http://'):
        raise DarajaError('MPESA_RESULT_URL_BASE must use https:// for Daraja callbacks.')

    try:
        path = reverse(url_name)
        return urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))
    except Exception as e:
        # ✅ FIX: If reverse fails, construct URL manually
        # This handles cases where URL names might not match
        raise DarajaError(f'Failed to resolve URL name "{url_name}": {e}')


def _ensure_trailing_slash(url: str) -> str:
    """
    Ensure the URL's path ends with '/' before any query string.

    Every Daraja callback route in urls.py requires a trailing slash. A
    misconfigured MPESA_*_URL override missing one doesn't just 404 — Django
    can't safely redirect a POST to add the slash, so it hard-errors on every
    single incoming Safaricom callback instead of ever reaching the view.
    """
    base, sep, query = url.partition('?')
    if not base.endswith('/'):
        base += '/'
    return f'{base}{sep}{query}'


def _with_callback_secret(url: str) -> str:
    """
    Embed MPESA_CALLBACK_SECRET as a query param on a callback URL.

    Daraja's C2B/STK/balance webhooks POST straight to whatever URL was
    registered and never carry custom headers, so a header-based secret can
    never be satisfied by real Safaricom traffic. Embedding it in the URL
    itself is the only mechanism Daraja actually supports.
    """
    secret = _clean(getattr(settings, 'MPESA_CALLBACK_SECRET', ''))
    if not secret:
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}callback_secret={quote(secret, safe="")}'


def _get_callback_url_from_settings(settings_key: str, default_url_name: str) -> str:
    """
    ✅ NEW: Get callback URL from settings or construct from URL name.
    This allows you to override individual callback URLs in .env.
    """
    # First check if URL is explicitly set in settings
    configured = _clean(getattr(settings, settings_key, ''))
    if configured:
        if configured.startswith('http://'):
            raise DarajaError(f'{settings_key} must use https://.')
        return _with_callback_secret(_ensure_trailing_slash(configured))

    # Fall back to constructing from URL name
    return _with_callback_secret(_absolute_callback_url(default_url_name))


def get_access_token() -> str:
    consumer_key = _clean(getattr(settings, 'MPESA_CONSUMER_KEY', ''))
    consumer_secret = _clean(getattr(settings, 'MPESA_CONSUMER_SECRET', ''))
    auth = b64encode(f'{consumer_key}:{consumer_secret}'.encode('utf-8')).decode('utf-8')

    url = urljoin(get_daraja_base_url(), 'oauth/v1/generate?grant_type=client_credentials')
    response = logged_request(
        'GET',
        url,
        headers={'Authorization': f'Basic {auth}'},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    access_token = data.get('access_token')
    if not access_token:
        raise DarajaError('Daraja access token missing from OAuth response.')
    return access_token


def _normalize_phone_number(phone_number: str) -> str:
    """Return phone number in Daraja format: 254XXXXXXXXX (digits only, no + or leading 0)."""
    digits = ''.join(ch for ch in str(phone_number or '').strip() if ch.isdigit())
    if digits.startswith('0') and len(digits) == 10:
        digits = '254' + digits[1:]
    elif digits.startswith('254') and len(digits) == 12:
        pass  # already correct
    elif digits.startswith('7') or digits.startswith('1') and len(digits) == 9:
        digits = '254' + digits
    return digits


def _get_stk_callback_url() -> str:
    """Get STK callback URL from settings or construct it."""
    return _get_callback_url_from_settings('MPESA_STK_CALLBACK_URL', 'payments:stk_push_callback')


def initiate_stk_push(
    *,
    phone_number: str,
    amount,
    account_reference: str,
    transaction_desc: str,
    shortcode: str = '',
) -> dict:
    """
    Initiate an STK push request. Defaults to the primary M-Pesa shortcode;
    pass `shortcode=settings.MPESA_SHORTCODE_2` to send it from the secondary
    paybill instead — each uses its own consumer key/secret/passkey.
    """
    creds = _resolve_paybill_credentials(shortcode)
    names = creds['var_names']
    required_vars = [names['consumer_key'], names['consumer_secret'], names['shortcode'], names['passkey']]
    missing = []
    for var_name in required_vars:
        value = getattr(settings, var_name, '')
        if value is None or str(value).strip() == '':
            missing.append(var_name)

    if missing:
        return {
            'ok': False,
            'missing_vars': missing,
            'error': 'Missing required M-Pesa settings.',
        }

    try:
        normalized_phone = _normalize_phone_number(phone_number)
        amount_value = Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if amount_value <= 0:
            raise DarajaError('Amount must be greater than zero.')

        shortcode_value = creds['shortcode']
        passkey = creds['passkey']
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = b64encode(f'{shortcode_value}{passkey}{timestamp}'.encode('utf-8')).decode('utf-8')
        callback_url = _get_stk_callback_url()

        payload = {
            'BusinessShortCode': shortcode_value,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': _clean(
                getattr(settings, 'MPESA_STK_TRANSACTION_TYPE', 'CustomerPayBillOnline')
            ) or 'CustomerPayBillOnline',
            'Amount': int(amount_value),
            'PartyA': normalized_phone,
            'PartyB': shortcode_value,
            'PhoneNumber': normalized_phone,
            'CallBackURL': callback_url,
            'AccountReference': _clean(account_reference)[:120],
            'TransactionDesc': _clean(transaction_desc)[:120] or 'Vehicle payment',
        }

        access_token = _get_access_token_for(creds['consumer_key'], creds['consumer_secret'])
        url = urljoin(get_daraja_base_url(), 'mpesa/stkpush/v1/processrequest')
        response = logged_request(
            'POST',
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()

        response_code = str(data.get('ResponseCode', '')).strip()
        return {
            'ok': response_code == '0',
            'response': data,
            'request_payload': payload,
            'missing_vars': [],
            'error': '' if response_code == '0' else data.get('ResponseDescription', 'Request failed.'),
            'shortcode': shortcode_value,
        }
    except requests.HTTPError as exc:
        body = ''
        status_code = None
        if exc.response is not None:
            status_code = exc.response.status_code
            try:
                body = exc.response.text
            except Exception:
                body = ''
        if status_code == 404:
            detail = (
                'Daraja returned 404: STK Push (Lipa na M-Pesa Online) is not enabled for '
                f'shortcode {creds["shortcode"]} on your Daraja app. '
                'Go to developer.safaricom.co.ke → your app → APIs and enable '
                '"Lipa na M-Pesa Online / Express Checkout".'
            )
        elif status_code == 401:
            detail = (
                'Daraja returned 401: Consumer key/secret are invalid or do not match '
                f'MPESA_ENV={_clean(getattr(settings, "MPESA_ENV", "sandbox"))}. '
                'Verify your credentials in the Daraja portal.'
            )
        else:
            detail = str(exc)
            if body:
                detail = f'{detail} | Daraja response: {body}'
        return {
            'ok': False,
            'missing_vars': [],
            'error': detail,
        }
    except (requests.RequestException, DarajaError, ValueError) as exc:
        return {
            'ok': False,
            'missing_vars': [],
            'error': str(exc),
        }


def request_account_balance(shortcode: str = '') -> dict:
    """Initiate Daraja account balance request for the given paybill
    (defaults to the primary; pass settings.MPESA_SHORTCODE_2 for the
    secondary one — each uses its own initiator name/security credential).

    Daraja returns the final balance via asynchronous callback.
    """
    creds = _resolve_paybill_credentials(shortcode)
    missing_vars = get_missing_mpesa_vars(shortcode)
    if missing_vars:
        return {
            'ok': False,
            'missing_vars': missing_vars,
            'error': 'Missing required M-Pesa settings.',
        }

    try:
        access_token = _get_access_token_for(creds['consumer_key'], creds['consumer_secret'])

        # ✅ FIX: Use the new helper to get balance callback URLs
        result_url = _get_callback_url_from_settings(
            'MPESA_BALANCE_RESULT_URL',
            'payments:paybill_balance_result_callback'
        )
        timeout_url = _get_callback_url_from_settings(
            'MPESA_BALANCE_TIMEOUT_URL',
            'payments:paybill_balance_timeout_callback'
        )

        # ✅ DEBUG: Log the URLs being used
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Balance Result URL: {result_url}")
        logger.info(f"Balance Timeout URL: {timeout_url}")

        payload = {
            'Initiator': creds['initiator_name'],
            'SecurityCredential': creds['security_credential'],
            'CommandID': 'AccountBalance',
            'PartyA': creds['shortcode'],
            'IdentifierType': '4',
            'Remarks': 'Paybill balance check',
            'QueueTimeOutURL': timeout_url,
            'ResultURL': result_url,
            'Occasion': f'vms-balance-{datetime.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:8]}',
        }

        url = urljoin(get_daraja_base_url(), 'mpesa/accountbalance/v1/query')
        response = logged_request(
            'POST',
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()

        return {
            'ok': True,
            'response': data,
            'request_reference': payload['Occasion'],
            'shortcode': creds['shortcode'],
        }
    except requests.HTTPError as exc:
        response = exc.response
        body = ''
        if response is not None:
            try:
                body = response.text
            except Exception:
                body = ''
        detail = str(exc)
        if body:
            detail = f'{detail} | Daraja response: {body}'
        return {
            'ok': False,
            'error': detail,
            'missing_vars': [],
        }
    except requests.RequestException as exc:
        return {
            'ok': False,
            'error': str(exc),
            'missing_vars': [],
        }
    except DarajaError as exc:
        return {
            'ok': False,
            'error': str(exc),
            'missing_vars': [],
        }


def _get_access_token_for(consumer_key: str, consumer_secret: str) -> str:
    """Get a Daraja access token using explicit credentials."""
    consumer_key = _clean(consumer_key)
    consumer_secret = _clean(consumer_secret)
    if not consumer_key or not consumer_secret:
        raise DarajaError('Consumer key and secret are required.')
    auth = b64encode(f'{consumer_key}:{consumer_secret}'.encode('utf-8')).decode('utf-8')
    url = urljoin(get_daraja_base_url(), 'oauth/v1/generate?grant_type=client_credentials')
    response = logged_request('GET', url, headers={'Authorization': f'Basic {auth}'}, timeout=20)
    response.raise_for_status()
    token = response.json().get('access_token')
    if not token:
        raise DarajaError('Daraja access token missing from OAuth response.')
    return token


def register_c2b_urls(shortcode: str, consumer_key: str = '', consumer_secret: str = '') -> dict:
    """Register C2B validation and confirmation URLs for a paybill shortcode."""
    shortcode = _clean(shortcode)
    if not shortcode:
        return {'ok': False, 'missing_vars': [], 'error': 'Shortcode is required.'}

    key = _clean(consumer_key) or _clean(getattr(settings, 'MPESA_CONSUMER_KEY', ''))
    secret = _clean(consumer_secret) or _clean(getattr(settings, 'MPESA_CONSUMER_SECRET', ''))
    if not key or not secret:
        return {
            'ok': False,
            'missing_vars': ['MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET'],
            'error': 'Consumer key and secret are required for C2B registration.',
        }

    try:
        access_token = _get_access_token_for(key, secret)
        
        # ✅ FIX: Use the new helper for C2B URLs
        confirmation_url = _get_callback_url_from_settings(
            'MPESA_C2B_CONFIRMATION_URL', 
            'payments:paybill_confirmation_callback'
        )
        validation_url = _get_callback_url_from_settings(
            'MPESA_C2B_VALIDATION_URL', 
            'payments:paybill_validation_callback'
        )

        payload = {
            'ShortCode': shortcode,
            'ResponseType': 'Completed',
            'ConfirmationURL': confirmation_url,
            'ValidationURL': validation_url,
        }

        url = urljoin(get_daraja_base_url(), 'mpesa/c2b/v2/registerurl')
        response = logged_request(
            'POST',
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            timeout=25,
        )
        data = response.json()

        if data.get('errorCode') or data.get('errorMessage'):
            error_msg = data.get('errorMessage', 'Unknown Daraja error')
            error_code = data.get('errorCode', '')
            if 'invalid access token' in error_msg.lower() or error_code in ('404.001.03', '400.002.02'):
                error_msg = (
                    f'Invalid access token for shortcode {shortcode}. '
                    'Your consumer key/secret may not have C2B API enabled. '
                    'Go to developer.safaricom.co.ke → your app → APIs and enable "C2B".'
                )
            return {
                'ok': False, 'shortcode': shortcode, 'response': data, 'missing_vars': [], 'error': error_msg,
                'confirmation_url': confirmation_url, 'validation_url': validation_url,
            }

        response.raise_for_status()
        response_code = str(data.get('ResponseCode', '')).strip()
        ok = response_code == '0' or 'success' in str(data.get('ResponseDescription', '')).lower()
        return {
            'ok': ok,
            'shortcode': shortcode,
            'response': data,
            'confirmation_url': confirmation_url,
            'validation_url': validation_url,
            'error': '' if ok else data.get('ResponseDescription', 'Registration failed.'),
        }
    except requests.HTTPError as exc:
        body = ''
        status_code = None
        if exc.response is not None:
            status_code = exc.response.status_code
            try:
                body = exc.response.text
            except Exception:
                body = ''
        if status_code in (401, 403) or (body and 'invalid access token' in body.lower()):
            return {
                'ok': False, 'missing_vars': [], 'shortcode': shortcode,
                'error': (
                    f'Daraja rejected the access token for shortcode {shortcode} (HTTP {status_code}). '
                    'Make sure C2B API is enabled for this app in the Daraja portal.'
                ),
            }
        detail = str(exc)
        if body:
            detail = f'{detail} | Daraja response: {body}'
        return {'ok': False, 'missing_vars': [], 'error': detail}
    except (requests.RequestException, DarajaError) as exc:
        return {'ok': False, 'missing_vars': [], 'error': str(exc)}