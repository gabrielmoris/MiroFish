"""
Optional username/password login.

Login is enabled only when both ``AUTH_USERNAME`` and ``AUTH_PASSWORD`` are
set. A successful login returns a signed, expiring bearer token. The signing
key is derived from ``SECRET_KEY`` and the configured credentials, so tokens
survive restarts and changing the password signs every session out. There is
no server-side session store.
"""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from typing import Any, Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..config import Config


TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
FAILED_LOGIN_DELAY_SECONDS = 1.0

_TOKEN_SALT = "mirofish-auth-token"
_KEY_DERIVATION_ITERATIONS = 200_000


def is_auth_enabled() -> bool:
    return bool(Config.AUTH_USERNAME and Config.AUTH_PASSWORD)


@lru_cache(maxsize=4)
def _signing_key(secret_key: str, username: str, password: str) -> bytes:
    # A slow derivation keeps a leaked token from being a cheap way to
    # brute-force the password, even when SECRET_KEY was left at its default.
    salt = f"{secret_key}\0{username}".encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _KEY_DERIVATION_ITERATIONS,
    )


def _serializer() -> URLSafeTimedSerializer:
    key = _signing_key(
        Config.SECRET_KEY,
        Config.AUTH_USERNAME,
        Config.AUTH_PASSWORD,
    )
    return URLSafeTimedSerializer(key, salt=_TOKEN_SALT)


def check_credentials(username: Any, password: Any) -> bool:
    if not is_auth_enabled():
        return False
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    # Compare both values even if the first one fails, in constant time.
    username_ok = hmac.compare_digest(
        username.encode("utf-8"),
        Config.AUTH_USERNAME.encode("utf-8"),
    )
    password_ok = hmac.compare_digest(
        password.encode("utf-8"),
        Config.AUTH_PASSWORD.encode("utf-8"),
    )
    return username_ok and password_ok


def issue_token() -> str:
    return _serializer().dumps({"user": Config.AUTH_USERNAME})


def verify_token(token: Optional[str]) -> bool:
    if not token or not is_auth_enabled():
        return False
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except BadSignature:  # also covers SignatureExpired
        return False
    return isinstance(data, dict) and data.get("user") == Config.AUTH_USERNAME


def token_from_request(request: Any) -> Optional[str]:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def is_public_path(path: str) -> bool:
    """Paths reachable without a login: everything outside /api and the auth endpoints."""
    return not path.startswith("/api/") or path.startswith("/api/auth/")
