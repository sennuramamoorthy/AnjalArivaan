"""Authentication primitives: password hashing, JWTs, TOTP."""
from datetime import datetime, timedelta, timezone
from typing import Any

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---- Passwords -------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plaintext matches the bcrypt hash."""
    return _pwd.verify(plain, hashed)


# ---- JWT -------------------------------------------------------------------

def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Mint a short-lived access JWT."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "typ": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Mint a refresh JWT (longer TTL)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "typ": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT, raising JWTError on invalid/expired tokens."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise JWTError(f"Invalid token: {e}") from e


# ---- MFA (TOTP) ------------------------------------------------------------

def generate_totp_secret() -> str:
    """Generate a fresh base32 TOTP secret."""
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_name: str) -> str:
    """Return an otpauth:// URI suitable for QR code generation."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name=settings.MFA_ISSUER
    )


def verify_totp(secret: str, code: str) -> bool:
    """Validate a 6-digit TOTP code with a ±1 step window."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
