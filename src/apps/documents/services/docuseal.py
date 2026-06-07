import base64

import requests
from django.conf import settings


class DocuSealError(Exception):
    """Raised when a DocuSeal API operation fails."""


def is_docuseal_configured():
    return bool(getattr(settings, 'DOCUSEAL_BASE_URL', '').strip() and getattr(settings, 'DOCUSEAL_API_KEY', '').strip())


def _base_url():
    return settings.DOCUSEAL_BASE_URL.rstrip('/')


def _api_headers():
    return {
        'X-Auth-Token': settings.DOCUSEAL_API_KEY,
        'Content-Type': 'application/json',
    }


def _extract_first_submitter(response_json):
    if isinstance(response_json, list):
        return response_json[0] if response_json else {}

    if isinstance(response_json, dict):
        submitters = response_json.get('submitters') or []
        if submitters:
            return submitters[0]

    return {}


def _choose_submission_endpoint(file_extension):
    ext = (file_extension or '').lower()
    endpoint_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
    }
    endpoint_suffix = endpoint_map.get(ext)
    if not endpoint_suffix:
        raise DocuSealError('DocuSeal signing currently supports PDF and DOCX files only.')

    return f"{_base_url()}/submissions/{endpoint_suffix}"


def create_signature_request(document, signer_name, signer_email, role=None):
    if not is_docuseal_configured():
        raise DocuSealError('DocuSeal is not configured. Set DOCUSEAL_BASE_URL and DOCUSEAL_API_KEY.')

    if not document.file:
        raise DocuSealError('Document file is missing.')

    role_name = role or getattr(settings, 'DOCUSEAL_DEFAULT_SIGNER_ROLE', 'Signer')
    endpoint = _choose_submission_endpoint(document.get_file_extension())

    file_bytes = document.file.read()
    document.file.seek(0)

    payload = {
        'name': document.title,
        'send_email': True,
        'documents': [
            {
                'name': document.title,
                'file': base64.b64encode(file_bytes).decode('ascii'),
            }
        ],
        'submitters': [
            {
                'name': signer_name,
                'email': signer_email,
                'role': role_name,
            }
        ],
    }

    timeout_seconds = int(getattr(settings, 'DOCUSEAL_TIMEOUT_SECONDS', 20))
    response = requests.post(endpoint, json=payload, headers=_api_headers(), timeout=timeout_seconds)

    if response.status_code >= 400:
        message = response.text
        try:
            message = response.json().get('error') or message
        except ValueError:
            pass
        raise DocuSealError(f'DocuSeal request failed: {message}')

    try:
        response_json = response.json()
    except ValueError as exc:
        raise DocuSealError('DocuSeal returned an invalid response payload.') from exc

    first_submitter = _extract_first_submitter(response_json)
    slug = first_submitter.get('slug')
    embed_src = first_submitter.get('embed_src')
    signing_link = embed_src or (f"{_base_url()}/s/{slug}" if slug else '')

    submission_id = first_submitter.get('submission_id')
    if not submission_id and isinstance(response_json, dict):
        submission_id = response_json.get('id')

    if not signing_link:
        raise DocuSealError('DocuSeal did not return a signing link.')

    return {
        'submission_id': str(submission_id or ''),
        'slug': slug or '',
        'signing_link': signing_link,
        'raw_response': response_json,
    }
