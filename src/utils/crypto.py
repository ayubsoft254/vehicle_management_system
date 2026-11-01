"""
Symmetric encryption for secrets stored in the database (M-Pesa keys etc.).

Uses Fernet with FIELD_ENCRYPTION_KEY from the environment. When that isn't
set, a key is derived from SECRET_KEY so the feature works out of the box —
but then rotating SECRET_KEY makes the stored secrets unreadable, so set
FIELD_ENCRYPTION_KEY in production (generate one with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_PREFIX = 'enc:'


@lru_cache(maxsize=1)
def _fernet():
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '') or ''
    if not key:
        digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(digest).decode('ascii')
    return Fernet(key.encode('ascii') if isinstance(key, str) else key)


def encrypt(value):
    """Encrypt a string; empty stays empty so 'not set' is still detectable."""
    if not value:
        return ''
    return _PREFIX + _fernet().encrypt(str(value).encode('utf-8')).decode('ascii')


def decrypt(value):
    """Decrypt a value produced by encrypt(). Plain (legacy) values pass
    through; an undecryptable token returns '' rather than leaking it."""
    if not value:
        return ''
    if not str(value).startswith(_PREFIX):
        return str(value)
    try:
        return _fernet().decrypt(str(value)[len(_PREFIX):].encode('ascii')).decode('utf-8')
    except InvalidToken:
        return ''
