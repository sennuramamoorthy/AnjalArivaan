"""AuthService unit tests — ported from Node.js AuthService.test.ts.

TDD: these tests define the contract. The service must satisfy them all.
"""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from src.modules.identity.services.auth_service import AuthService
from src.modules.identity.adapters.password_hasher import MockPasswordHasher
from src.modules.identity.adapters.token_store import MockTokenStore
from src.modules.identity.adapters.totp_service import MockTotpService
from src.modules.identity.repositories.in_memory_user_repo import InMemoryUserRepository
from src.infra.logger import create_logger
from src.shared.crypto.encryption import encrypt
from src.shared.domain.errors import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    MfaRequiredError,
    InvalidMfaCodeError,
    TokenInvalidError,
    ValidationError,
)

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

FIELD_ENC_KEY = "a" * 64


def make_auth_service(
    repo=None, hasher=None, store=None, totp=None, mfa_enabled=True
) -> AuthService:
    return AuthService(
        user_repo=repo or InMemoryUserRepository(),
        password_hasher=hasher or MockPasswordHasher(),
        token_store=store or MockTokenStore(),
        totp_service=totp or MockTotpService(),
        logger=create_logger("identity-test"),
        jwt_private_key=PRIVATE_KEY,
        jwt_public_key=PUBLIC_KEY,
        field_encryption_key=FIELD_ENC_KEY,
        mfa_globally_enabled=mfa_enabled,
    )


# ── Register ─────────────────────────────────────────────────────────────────

class TestRegister:
    @pytest.mark.asyncio
    async def test_register_returns_public_user(self):
        svc = make_auth_service()
        user = await svc.register({"email": "test@example.com", "password": "password123", "name": "Test"})
        assert user.id
        assert user.email == "test@example.com"
        assert user.role == "STAFF"

    @pytest.mark.asyncio
    async def test_register_hashes_password(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "hash@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("hash@example.com")
        assert user.password_hash == "hashed:password123"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_throws(self):
        svc = make_auth_service()
        await svc.register({"email": "dup@example.com", "password": "password123", "name": "Test"})
        with pytest.raises(UserAlreadyExistsError):
            await svc.register({"email": "dup@example.com", "password": "password123", "name": "Test"})

    @pytest.mark.asyncio
    async def test_register_invalid_email_throws(self):
        svc = make_auth_service()
        with pytest.raises(ValidationError):
            await svc.register({"email": "not-an-email", "password": "password123", "name": "Test"})

    @pytest.mark.asyncio
    async def test_register_short_password_throws(self):
        svc = make_auth_service()
        with pytest.raises(ValidationError):
            await svc.register({"email": "short@example.com", "password": "abc", "name": "Test"})


# ── Login ────────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_returns_tokens(self):
        svc = make_auth_service()
        await svc.register({"email": "login@example.com", "password": "password123", "name": "Test"})
        tokens = await svc.login({"email": "login@example.com", "password": "password123"})
        assert "accessToken" in tokens
        assert "refreshToken" in tokens

    @pytest.mark.asyncio
    async def test_login_wrong_password_throws(self):
        svc = make_auth_service()
        await svc.register({"email": "wrong@example.com", "password": "password123", "name": "Test"})
        with pytest.raises(InvalidCredentialsError):
            await svc.login({"email": "wrong@example.com", "password": "wrongpass"})

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_throws(self):
        svc = make_auth_service()
        with pytest.raises(InvalidCredentialsError):
            await svc.login({"email": "ghost@example.com", "password": "password123"})

    @pytest.mark.asyncio
    async def test_login_mfa_required_when_enabled(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "mfa@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("mfa@example.com")
        encrypted_secret = encrypt("MOCKSECRET", FIELD_ENC_KEY)
        await repo.update(user.id, {"mfa_enabled": True, "mfa_secret": encrypted_secret})

        with pytest.raises(MfaRequiredError):
            await svc.login({"email": "mfa@example.com", "password": "password123"})

    @pytest.mark.asyncio
    async def test_login_mfa_success(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "mfaok@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("mfaok@example.com")
        encrypted_secret = encrypt("MOCKSECRET", FIELD_ENC_KEY)
        await repo.update(user.id, {"mfa_enabled": True, "mfa_secret": encrypted_secret})

        tokens = await svc.login({
            "email": "mfaok@example.com",
            "password": "password123",
            "mfaCode": "123456",  # MockTotpService.VALID_CODE
        })
        assert "accessToken" in tokens

    @pytest.mark.asyncio
    async def test_login_mfa_bad_code_throws(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "mfabad@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("mfabad@example.com")
        encrypted_secret = encrypt("MOCKSECRET", FIELD_ENC_KEY)
        await repo.update(user.id, {"mfa_enabled": True, "mfa_secret": encrypted_secret})

        with pytest.raises(InvalidMfaCodeError):
            await svc.login({
                "email": "mfabad@example.com",
                "password": "password123",
                "mfaCode": "000000",
            })


# ── Refresh ──────────────────────────────────────────────────────────────────

class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self):
        svc = make_auth_service()
        await svc.register({"email": "refresh@example.com", "password": "password123", "name": "Test"})
        tokens = await svc.login({"email": "refresh@example.com", "password": "password123"})
        new_tokens = await svc.refresh_token(tokens["refreshToken"])
        assert "accessToken" in new_tokens
        assert new_tokens["accessToken"] != tokens["accessToken"]

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_throws(self):
        svc = make_auth_service()
        with pytest.raises(TokenInvalidError):
            await svc.refresh_token("nonexistent-token-id")


# ── Logout ───────────────────────────────────────────────────────────────────

class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_invalidates_refresh_token(self):
        store = MockTokenStore()
        svc = make_auth_service(store=store)
        await svc.register({"email": "logout@example.com", "password": "password123", "name": "Test"})
        tokens = await svc.login({"email": "logout@example.com", "password": "password123"})
        await svc.logout(tokens["refreshToken"])
        with pytest.raises(TokenInvalidError):
            await svc.refresh_token(tokens["refreshToken"])


# ── MFA Setup ────────────────────────────────────────────────────────────────

class TestMfaSetup:
    @pytest.mark.asyncio
    async def test_setup_returns_secret_and_qr(self):
        svc = make_auth_service()
        await svc.register({"email": "mfasetup@example.com", "password": "password123", "name": "Test"})
        user = await svc._user_repo.find_by_email("mfasetup@example.com")
        result = await svc.setup_mfa(user.id)
        assert "secret" in result
        assert "qrCodeUri" in result
        assert "backupCodes" in result

    @pytest.mark.asyncio
    async def test_verify_setup_enables_mfa(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "mfaenable@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("mfaenable@example.com")
        await svc.setup_mfa(user.id)
        result = await svc.verify_mfa_setup(user.id, "123456")  # MockTotpService.VALID_CODE
        assert result["success"] is True
        updated = await repo.find_by_id(user.id)
        assert updated.mfa_enabled is True

    @pytest.mark.asyncio
    async def test_verify_setup_bad_code_throws(self):
        repo = InMemoryUserRepository()
        svc = make_auth_service(repo=repo)
        await svc.register({"email": "mfafail@example.com", "password": "password123", "name": "Test"})
        user = await repo.find_by_email("mfafail@example.com")
        await svc.setup_mfa(user.id)
        with pytest.raises(InvalidMfaCodeError):
            await svc.verify_mfa_setup(user.id, "000000")


# ── JWT ──────────────────────────────────────────────────────────────────────

class TestJwt:
    @pytest.mark.asyncio
    async def test_access_token_is_valid_jwt(self):
        svc = make_auth_service()
        await svc.register({"email": "jwt@example.com", "password": "password123", "name": "Test"})
        tokens = await svc.login({"email": "jwt@example.com", "password": "password123"})
        payload = svc.verify_access_token(tokens["accessToken"])
        assert payload["email"] == "jwt@example.com"
        assert payload["role"] == "STAFF"
        assert "sub" in payload
