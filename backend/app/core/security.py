"""Password hashing, session tokens and at-rest encryption.

- Passwords: argon2 (used by services/auth_service.py).
- Session tokens: random values; only an HMAC of each is stored (models/session.py).
- Encryption: Fernet with ENCRYPTION_KEY, for provider credentials such as the SimpleFIN access
  URL (services/connection_service.py encrypts, services/sync_service.py decrypts).
"""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import ConfigError

_hasher = PasswordHasher()
# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("fintrack-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Check a password. Pass None for an unknown user; it still costs the same time."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when argon2's recommended parameters changed since this hash was made."""
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    """A random, URL-safe token (session cookies, and invite links later)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored only as keyed hashes, so a leaked DB can't be used to log in."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()


def _fernet() -> Fernet:
    """Build the cipher from ENCRYPTION_KEY, with errors that explain how to fix the key."""
    key = get_settings().encryption_key
    if not key:
        raise ConfigError(
            "ENCRYPTION_KEY is not set. It's a key FinTrack generates itself (not from SimpleFIN): "
            "run `fintrack gen-keys` and paste it into backend/.env."
        )
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise ConfigError(
            "ENCRYPTION_KEY is not a valid key. It must be the 44-character value printed by "
            "`fintrack gen-keys` (not a SimpleFIN token)."
        ) from exc


def check_encryption_key() -> None:
    """Fails fast on a bad ENCRYPTION_KEY, before a single-use setup token is spent."""
    _fernet()


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ConfigError(
            "Stored credentials can't be decrypted. Did ENCRYPTION_KEY change?"
        ) from exc
