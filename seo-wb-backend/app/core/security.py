import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Request, Response
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.errors import AppError


HASH_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(HASH_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_{HASH_ALGORITHM}${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded_hash.split("$")
        if algorithm != f"pbkdf2_{HASH_ALGORITHM}":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(HASH_ALGORITHM, password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(settings: Settings, subject: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.app_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AppError("token_expired", "Access token expired.", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError("invalid_token", "Invalid access token.", 401) from exc


def request_fingerprint(settings: Settings, request: Request) -> str:
    user_agent = request.headers.get("user-agent", "")
    raw = f"{settings.app_secret_key}:{user_agent}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def assert_token_fingerprint(settings: Settings, request: Request, payload: dict[str, Any]) -> None:
    if not settings.jwt_bind_user_agent:
        return
    expected = payload.get("fp")
    if not expected or not hmac.compare_digest(str(expected), request_fingerprint(settings, request)):
        raise AppError("invalid_token_fingerprint", "Access token fingerprint is invalid.", 401)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    settings: Settings,
    response: Response,
    access_token: str,
    csrf_token: str,
    *,
    auth_cookie_name: str | None = None,
    csrf_cookie_name: str | None = None,
) -> None:
    max_age = settings.jwt_expire_minutes * 60
    access_cookie = auth_cookie_name or settings.auth_cookie_name
    csrf_cookie = csrf_cookie_name or settings.csrf_cookie_name
    response.set_cookie(
        access_cookie,
        access_token,
        max_age=max_age,
        httponly=True,
        secure=settings.should_secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        csrf_cookie,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.should_secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(
    settings: Settings,
    response: Response,
    *,
    auth_cookie_name: str | None = None,
    csrf_cookie_name: str | None = None,
) -> None:
    response.delete_cookie(auth_cookie_name or settings.auth_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(csrf_cookie_name or settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


def assert_csrf(
    settings: Settings,
    request: Request,
    payload: dict[str, Any],
    token_source: str,
    *,
    csrf_cookie_name: str | None = None,
) -> None:
    if token_source != "cookie" or request.method.upper() not in UNSAFE_METHODS:
        return
    csrf_cookie = request.cookies.get(csrf_cookie_name or settings.csrf_cookie_name)
    csrf_header = request.headers.get("x-csrf-token")
    csrf_claim = payload.get("csrf")
    if not csrf_cookie or not csrf_header or not csrf_claim:
        raise AppError("csrf_required", "CSRF token is required.", 403)
    if not hmac.compare_digest(csrf_cookie, csrf_header) or not hmac.compare_digest(csrf_cookie, str(csrf_claim)):
        raise AppError("csrf_invalid", "CSRF token is invalid.", 403)


def _fernet_key(settings: Settings) -> bytes:
    raw = settings.encryption_key or settings.app_secret_key
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(settings: Settings, value: str) -> str:
    return Fernet(_fernet_key(settings)).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(settings: Settings, encrypted_value: str) -> str:
    try:
        return Fernet(_fernet_key(settings)).decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError("secret_decryption_failed", "Stored secret could not be decrypted.", 500) from exc
