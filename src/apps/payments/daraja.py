"""Daraja API helpers for paybill operations."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime
import uuid
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.urls import reverse


class DarajaError(Exception):
    """Raised when Daraja API operations fail."""


def get_daraja_base_url() -> str:
    env = (settings.MPESA_ENV or 'sandbox').strip().lower()
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
    base_url = (settings.MPESA_RESULT_URL_BASE or '').strip()
    if not base_url:
        raise DarajaError('MPESA_RESULT_URL_BASE is not configured.')

    path = reverse(url_name)
    return urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))


def get_access_token() -> str:
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
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
            'Initiator': settings.MPESA_INITIATOR_NAME,
            'SecurityCredential': settings.MPESA_SECURITY_CREDENTIAL,
            'CommandID': 'AccountBalance',
            'PartyA': str(settings.MPESA_SHORTCODE),
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
