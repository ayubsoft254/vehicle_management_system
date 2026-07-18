"""
Verbose request/response logging for Daraja (M-Pesa) callbacks.

Every helper here is a no-op unless settings.DEBUG is True — in production
(DEBUG=False) the decorator/wrapper just calls straight through with zero
overhead, so no M-Pesa payload, phone number, or credential ever reaches a
production log.

Wire-up:
    - `log_incoming_callback` decorates the five Daraja callback views
      (validation, confirmation, STK, balance-result, balance-timeout).
    - `logged_request` replaces direct `requests.get`/`requests.post` calls
      in daraja.py for outgoing calls to Safaricom.
"""
from __future__ import annotations

import functools
import json
import logging
import time
import traceback
import uuid
from datetime import datetime

from django.conf import settings

logger = logging.getLogger('payments.callback_debug')

_SEPARATOR = '=' * 100

# Any key containing one of these (case/underscore/dash-insensitive) has its
# value masked before logging — even in debug mode, credentials shouldn't
# land in a log file verbatim.
_SENSITIVE_KEY_MARKERS = (
    'authorization', 'cookie', 'secret', 'token', 'password',
    'securitycredential', 'apikey',
)


def _looks_sensitive(key) -> bool:
    normalized = str(key).lower().replace('_', '').replace('-', '')
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_mapping(mapping):
    """Mask values for any credential-shaped key, recursively."""
    if not isinstance(mapping, dict):
        return mapping
    redacted = {}
    for key, value in mapping.items():
        if _looks_sensitive(key):
            redacted[key] = '***REDACTED***'
        elif isinstance(value, dict):
            redacted[key] = _redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def _get_client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _safe_json(value) -> str:
    try:
        return json.dumps(value, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def log_incoming_callback(endpoint_name=None):
    """
    Decorator for Daraja callback views. When settings.DEBUG is True, logs a
    full structured dump of the incoming request (headers, IP, query params,
    form data, raw body, parsed JSON) and the outgoing response (status,
    body), bracketed by clear start/end separators, plus full tracebacks for
    any exception raised while processing. No-ops in production.
    """
    def decorator(view_func):
        name = endpoint_name or view_func.__name__

        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not settings.DEBUG:
                return view_func(request, *args, **kwargs)

            request_id = uuid.uuid4().hex[:12]
            start = time.monotonic()

            raw_body = b''
            try:
                raw_body = request.body
            except Exception as exc:
                logger.debug('Could not read request body: %s', exc)
            body_text = raw_body.decode('utf-8', errors='replace') if raw_body else ''

            parsed_json = None
            if body_text:
                try:
                    parsed_json = json.loads(body_text)
                except (json.JSONDecodeError, ValueError):
                    parsed_json = None

            headers = dict(request.headers)
            auth_header_names = [
                k for k in headers
                if any(w in k.lower() for w in ('auth', 'signature', 'secret', 'token'))
            ]

            logger.debug(_SEPARATOR)
            logger.debug('[CALLBACK START] %s | id=%s | %s', name, request_id, datetime.now().isoformat())
            logger.debug(_SEPARATOR)
            logger.debug('Endpoint         : %s', name)
            logger.debug('Method           : %s', request.method)
            logger.debug('Full URL         : %s', request.build_absolute_uri())
            logger.debug('Client IP        : %s', _get_client_ip(request))
            logger.debug('Query Params     : %s', _safe_json(dict(request.GET)))
            logger.debug('Headers          : %s', _safe_json(_redact_mapping(headers)))
            logger.debug('Auth/Sig Headers : %s', auth_header_names or '(none present)')
            logger.debug('Form Data        : %s', _safe_json(dict(request.POST)) if request.POST else '(none)')
            logger.debug('Raw Body         : %s', body_text or '(empty)')
            logger.debug(
                'Parsed JSON      : %s',
                _safe_json(parsed_json) if parsed_json is not None else '(not JSON / not applicable)'
            )

            response = None
            try:
                response = view_func(request, *args, **kwargs)
                return response
            except Exception:
                logger.debug('EXCEPTION while processing callback %s:', name)
                logger.debug(traceback.format_exc())
                raise
            finally:
                duration_ms = (time.monotonic() - start) * 1000
                if response is not None:
                    body_preview = getattr(response, 'content', b'')
                    try:
                        body_preview = body_preview.decode('utf-8', errors='replace')
                    except Exception:
                        body_preview = str(body_preview)
                    logger.debug('Response Status  : %s', getattr(response, 'status_code', 'unknown'))
                    logger.debug('Response Body    : %s', body_preview)
                logger.debug('Duration         : %.2fms', duration_ms)
                logger.debug(_SEPARATOR)
                logger.debug('[CALLBACK END] %s | id=%s', name, request_id)
                logger.debug(_SEPARATOR)

        return wrapper
    return decorator


def logged_request(method: str, url: str, **kwargs):
    """
    Drop-in replacement for requests.request (and the get/post call sites in
    daraja.py) for outgoing calls to Safaricom. When settings.DEBUG is True,
    logs the full outgoing request and response — redacting credential-shaped
    fields — plus total duration, bracketed by clear separators, and full
    exception details on failure. In production this is a silent, zero-
    overhead pass-through to `requests.request`.
    """
    import requests

    if not settings.DEBUG:
        return requests.request(method, url, **kwargs)

    logger.debug(_SEPARATOR)
    logger.debug('[OUTGOING REQUEST START] %s %s | %s', method.upper(), url, datetime.now().isoformat())
    logger.debug(_SEPARATOR)
    logger.debug('Headers  : %s', _safe_json(_redact_mapping(kwargs.get('headers') or {})))
    payload = kwargs.get('json') if kwargs.get('json') is not None else kwargs.get('data')
    logger.debug('Payload  : %s', _safe_json(_redact_mapping(payload)) if payload else '(none)')

    start = time.monotonic()
    try:
        response = requests.request(method, url, **kwargs)
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.debug('REQUEST ERROR after %.2fms: %s: %s', duration_ms, type(exc).__name__, exc)
        logger.debug(traceback.format_exc())
        logger.debug(_SEPARATOR)
        logger.debug('[OUTGOING REQUEST END] %s %s (error)', method.upper(), url)
        logger.debug(_SEPARATOR)
        raise

    duration_ms = (time.monotonic() - start) * 1000
    try:
        body_preview = response.text[:5000]
    except Exception:
        body_preview = '(unreadable response body)'
    logger.debug('Response Status  : %s', response.status_code)
    logger.debug('Response Headers : %s', _safe_json(dict(response.headers)))
    logger.debug('Response Body    : %s', body_preview)
    logger.debug('Duration         : %.2fms', duration_ms)
    logger.debug(_SEPARATOR)
    logger.debug('[OUTGOING REQUEST END] %s %s', method.upper(), url)
    logger.debug(_SEPARATOR)
    return response
