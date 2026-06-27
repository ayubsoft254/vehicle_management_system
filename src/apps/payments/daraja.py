"""Daraja API helpers for paybill operations."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime
import uuid
from urllib.parse import urljoin
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.urls import reverse


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


def get_required_mpesa_vars() -> list[str]:
    return [
        'MPESA_CONSUMER_KEY',
        'MPESA_CONSUMER_SECRET',
        'MPESA_SHORTCODE',
        'MPESA_INITIATOR_NAME',
        'MPESA_SECURITY_CREDENTIAL',
        'MPESA_RESULT_URL_BASE',
    ]


def get_missing_mpesa_vars() -> list[str]:
    missing = []
    for var_name in get_required_mpesa_vars():
        value = getattr(settings, var_name, '')
        if value is None or str(value).strip() == '':
            missing.append(var_name)
    return missing


def mpesa_is_configured() -> bool:
    return not get_missing_mpesa_vars()


def _absolute_callback_url(url_name: str) -> str:
    base_url = _clean(getattr(settings, 'MPESA_RESULT_URL_BASE', ''))
    if not base_url:
        raise DarajaError('MPESA_RESULT_URL_BASE is not configured.')
    if base_url.startswith('http://'):
        raise DarajaError('MPESA_RESULT_URL_BASE must use https:// for Daraja callbacks.')

    path = reverse(url_name)
    return urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))


def get_access_token() -> str:
    consumer_key = _clean(getattr(settings, 'MPESA_CONSUMER_KEY', ''))
    consumer_secret = _clean(getattr(settings, 'MPESA_CONSUMER_SECRET', ''))
    auth = b64encode(f'{consumer_key}:{consumer_secret}'.encode('utf-8')).decode('utf-8')

    url = urljoin(get_daraja_base_url(), 'oauth/v1/generate?grant_type=client_credentials')
    response = requests.get(
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
    configured = _clean(getattr(settings, 'MPESA_STK_CALLBACK_URL', ''))
    if configured:
        if configured.startswith('http://'):
            raise DarajaError('MPESA_STK_CALLBACK_URL must use https://.')
        return configured
    return _absolute_callback_url('payments:stk_push_callback')


def initiate_stk_push(
    *,
    phone_number: str,
    amount,
    account_reference: str,
    transaction_desc: str,
) -> dict:
    """Initiate an STK push request to the configured M-Pesa shortcode."""
    required_vars = [
        'MPESA_CONSUMER_KEY',
        'MPESA_CONSUMER_SECRET',
        'MPESA_SHORTCODE',
        'MPESA_PASSKEY',
    ]
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

        shortcode = _clean(getattr(settings, 'MPESA_SHORTCODE', ''))
        passkey = _clean(getattr(settings, 'MPESA_PASSKEY', ''))
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = b64encode(f'{shortcode}{passkey}{timestamp}'.encode('utf-8')).decode('utf-8')
        callback_url = _get_stk_callback_url()

        payload = {
            'BusinessShortCode': shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': _clean(
                getattr(settings, 'MPESA_STK_TRANSACTION_TYPE', 'CustomerPayBillOnline')
            ) or 'CustomerPayBillOnline',
            'Amount': int(amount_value),
            'PartyA': normalized_phone,
            'PartyB': shortcode,
            'PhoneNumber': normalized_phone,
            'CallBackURL': callback_url,
            'AccountReference': _clean(account_reference)[:120],
            'TransactionDesc': _clean(transaction_desc)[:120] or 'Vehicle payment',
        }

        access_token = get_access_token()
        url = urljoin(get_daraja_base_url(), 'mpesa/stkpush/v1/processrequest')
        response = requests.post(
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
                f'shortcode {shortcode} on your Daraja app. '
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


def request_account_balance() -> dict:
    """Initiate Daraja account balance request.

    Daraja returns the final balance via asynchronous callback.
    """
    missing_vars = get_missing_mpesa_vars()
    if missing_vars:
        return {
            'ok': False,
            'missing_vars': missing_vars,
            'error': 'Missing required M-Pesa settings.',
        }

    try:
        access_token = get_access_token()
        result_url = _absolute_callback_url('payments:paybill_balance_result_callback')
        timeout_url = _absolute_callback_url('payments:paybill_balance_timeout_callback')

        payload = {
            'Initiator': _clean(getattr(settings, 'MPESA_INITIATOR_NAME', '')),
            'SecurityCredential': _clean(getattr(settings, 'MPESA_SECURITY_CREDENTIAL', '')),
            'CommandID': 'AccountBalance',
            'PartyA': _clean(getattr(settings, 'MPESA_SHORTCODE', '')),
            'IdentifierType': '4',
            'Remarks': 'Paybill balance check',
            'QueueTimeOutURL': timeout_url,
            'ResultURL': result_url,
            'Occasion': f'vms-balance-{datetime.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:8]}',
        }

        url = urljoin(get_daraja_base_url(), 'mpesa/accountbalance/v1/query')
        response = requests.post(
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
    response = requests.get(url, headers={'Authorization': f'Basic {auth}'}, timeout=20)
    response.raise_for_status()
    token = response.json().get('access_token')
    if not token:
        raise DarajaError('Daraja access token missing from OAuth response.')
    return token


def register_c2b_urls(shortcode: str, consumer_key: str = '', consumer_secret: str = '') -> dict:
    """Register C2B validation and confirmation URLs for a paybill shortcode.

    Must be called once per shortcode so Safaricom knows where to POST C2B
    callbacks.  Pass explicit consumer_key/consumer_secret when the paybill
    belongs to a different Safaricom account than the primary shortcode.
    """
    shortcode = _clean(shortcode)
    if not shortcode:
        return {'ok': False, 'missing_vars': [], 'error': 'Shortcode is required.'}

    # Fall back to primary credentials when none supplied
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
        confirmation_url = _absolute_callback_url('payments:paybill_confirmation_callback')
        validation_url = _absolute_callback_url('payments:paybill_validation_callback')

        payload = {
            'ShortCode': shortcode,
            'ResponseType': 'Completed',
            'ConfirmationURL': confirmation_url,
            'ValidationURL': validation_url,
        }

        url = urljoin(get_daraja_base_url(), 'mpesa/c2b/v2/registerurl')
        response = requests.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            timeout=25,
        )
        data = response.json()

        # Safaricom uses errorCode/errorMessage for errors, ResponseCode/ResponseDescription for success
        if data.get('errorCode') or data.get('errorMessage'):
            error_msg = data.get('errorMessage', 'Unknown Daraja error')
            error_code = data.get('errorCode', '')
            if 'invalid access token' in error_msg.lower() or error_code in ('404.001.03', '400.002.02'):
                error_msg = (
                    f'Invalid access token for shortcode {shortcode}. '
                    'Your consumer key/secret may not have C2B API enabled. '
                    'Go to developer.safaricom.co.ke → your app → APIs and enable "C2B".'
                )
            return {'ok': False, 'shortcode': shortcode, 'response': data, 'missing_vars': [], 'error': error_msg}

        response.raise_for_status()
        response_code = str(data.get('ResponseCode', '')).strip()
        ok = response_code == '0' or 'success' in str(data.get('ResponseDescription', '')).lower()
        return {
            'ok': ok,
            'shortcode': shortcode,
            'response': data,
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
