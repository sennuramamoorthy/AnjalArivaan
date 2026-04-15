"""Authenticate middleware tests — ported from Node.js authenticate.test.ts.

Tests JWT verification via FastAPI Depends pattern.
"""

import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt as jose_jwt

from src.modules.identity.services.auth_service import AuthService
from src.modules.identity.adapters.password_hasher import MockPasswordHasher
from src.modules.identity.adapters.token_store import MockTokenStore
from src.modules.identity.adapters.totp_service import MockTotpService
from src.modules.identity.repositories.in_memory_user_repo import InMemoryUserRepository
from src.shared.middleware.authenticate import authenticate_dependency
from src.shared.domain.errors import TokenExpiredError, TokenInvalidError, UnauthorizedError
from src.infra.logger import create_logger

# Generate RSA key pair for tests
_private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY = _private_key_obj.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_KEY = _private_key_obj.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

# Second key pair (wrong key)
_wrong_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
WRONG_PRIVATE_KEY = _wrong_key_obj.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()

FIELD_ENC_KEY = "b" * 64


def make_auth_service() -> AuthService:
    return AuthService(
        user_repo=InMemoryUserRepository(),
        password_hasher=MockPasswordHasher(),
        token_store=MockTokenStore(),
        totp_service=MockTotpService(),
        logger=create_logger("identity-test"),
        jwt_private_key=PRIVATE_KEY,
        jwt_public_key=PUBLIC_KEY,
        field_encryption_key=FIELD_ENC_KEY,
    )


def make_valid_token(key: str = PRIVATE_KEY) -> str:
    now = int(time.time())
    return jose_jwt.encode(
        {"sub": "user-1", "role": "STAFF", "email": "test@example.com", "jti": "jti-1", "iat": now, "exp": now + 900},
        key,
        algorithm="RS256",
    )


def make_expired_token() -> str:
    now = int(time.time())
    return jose_jwt.encode(
        {"sub": "user-1", "role": "STAFF", "email": "test@example.com", "jti": "jti-2", "iat": now - 120, "exp": now - 60},
        PRIVATE_KEY,
        algorithm="RS256",
    )


class TestAuthenticate:
    def setup_method(self):
        self.auth_service = make_auth_service()
        self.authenticate = authenticate_dependency(self.auth_service)

    def test_returns_user_on_valid_jwt(self):
        token = make_valid_token()
        user = self.authenticate(f"Bearer {token}")
        assert user["id"] == "user-1"
        assert user["role"] == "STAFF"
        assert user["email"] == "test@example.com"

    def test_raises_unauthorized_for_missing_header(self):
        with pytest.raises(UnauthorizedError):
            self.authenticate(None)

    def test_raises_unauthorized_for_empty_header(self):
        with pytest.raises(UnauthorizedError):
            self.authenticate("")

    def test_raises_unauthorized_for_non_bearer_header(self):
        with pytest.raises(UnauthorizedError):
            self.authenticate("Basic abc123")

    def test_raises_token_invalid_for_malformed_token(self):
        with pytest.raises(TokenInvalidError):
            self.authenticate("Bearer not.a.valid.jwt")

    def test_raises_token_expired_for_expired_token(self):
        token = make_expired_token()
        with pytest.raises(TokenExpiredError):
            self.authenticate(f"Bearer {token}")

    def test_raises_token_invalid_for_wrong_signing_key(self):
        token = make_valid_token(key=WRONG_PRIVATE_KEY)
        with pytest.raises(TokenInvalidError):
            self.authenticate(f"Bearer {token}")
