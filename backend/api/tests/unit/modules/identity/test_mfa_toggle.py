"""MFA toggle tests — ported from Node.js MfaToggle.test.ts.

Tests MFA globally enabled vs disabled behavior.
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
from src.shared.domain.errors import MfaRequiredError, MfaDisabledError

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


def make_svc(mfa_enabled: bool, repo=None) -> AuthService:
    return AuthService(
        user_repo=repo or InMemoryUserRepository(),
        password_hasher=MockPasswordHasher(),
        token_store=MockTokenStore(),
        totp_service=MockTotpService(),
        logger=create_logger("identity-test"),
        jwt_private_key=PRIVATE_KEY,
        jwt_public_key=PUBLIC_KEY,
        field_encryption_key=FIELD_ENC_KEY,
        mfa_globally_enabled=mfa_enabled,
    )


class TestMfaEnabled:
    @pytest.mark.asyncio
    async def test_login_requires_mfa_when_user_has_it(self):
        repo = InMemoryUserRepository()
        svc = make_svc(True, repo)
        await svc.register({"email": "mfa-on@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-on@example.com")
        encrypted = encrypt("MOCKSECRET", FIELD_ENC_KEY)
        await repo.update(user.id, {"mfa_enabled": True, "mfa_secret": encrypted})

        with pytest.raises(MfaRequiredError):
            await svc.login({"email": "mfa-on@example.com", "password": "password123"})

    @pytest.mark.asyncio
    async def test_setup_mfa_works(self):
        repo = InMemoryUserRepository()
        svc = make_svc(True, repo)
        await svc.register({"email": "mfa-on@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-on@example.com")
        result = await svc.setup_mfa(user.id)
        assert "secret" in result

    @pytest.mark.asyncio
    async def test_verify_setup_works(self):
        repo = InMemoryUserRepository()
        svc = make_svc(True, repo)
        await svc.register({"email": "mfa-on@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-on@example.com")
        await svc.setup_mfa(user.id)
        result = await svc.verify_mfa_setup(user.id, "123456")
        assert result["success"] is True


class TestMfaDisabled:
    @pytest.mark.asyncio
    async def test_login_skips_mfa_when_disabled(self):
        repo = InMemoryUserRepository()
        svc = make_svc(False, repo)
        await svc.register({"email": "mfa-off@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-off@example.com")
        encrypted = encrypt("MOCKSECRET", FIELD_ENC_KEY)
        await repo.update(user.id, {"mfa_enabled": True, "mfa_secret": encrypted})

        tokens = await svc.login({"email": "mfa-off@example.com", "password": "password123"})
        assert "accessToken" in tokens

    @pytest.mark.asyncio
    async def test_setup_mfa_throws_when_disabled(self):
        repo = InMemoryUserRepository()
        svc = make_svc(False, repo)
        await svc.register({"email": "mfa-off@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-off@example.com")
        with pytest.raises(MfaDisabledError):
            await svc.setup_mfa(user.id)

    @pytest.mark.asyncio
    async def test_verify_setup_throws_when_disabled(self):
        repo = InMemoryUserRepository()
        svc = make_svc(False, repo)
        await svc.register({"email": "mfa-off@example.com", "password": "password123", "name": "T"})
        user = await repo.find_by_email("mfa-off@example.com")
        with pytest.raises(MfaDisabledError):
            await svc.verify_mfa_setup(user.id, "123456")

    @pytest.mark.asyncio
    async def test_login_with_mfa_code_ignored_when_disabled(self):
        repo = InMemoryUserRepository()
        svc = make_svc(False, repo)
        await svc.register({"email": "mfa-off@example.com", "password": "password123", "name": "T"})
        tokens = await svc.login({
            "email": "mfa-off@example.com",
            "password": "password123",
            "mfaCode": "123456",
        })
        assert "accessToken" in tokens


class TestMfaDefault:
    @pytest.mark.asyncio
    async def test_mfa_enabled_by_default(self):
        """AuthService constructor defaults to mfa_globally_enabled=True."""
        svc = AuthService(
            user_repo=InMemoryUserRepository(),
            password_hasher=MockPasswordHasher(),
            token_store=MockTokenStore(),
            totp_service=MockTotpService(),
            logger=create_logger("identity-test"),
            jwt_private_key=PRIVATE_KEY,
            jwt_public_key=PUBLIC_KEY,
            field_encryption_key=FIELD_ENC_KEY,
        )
        # Should be able to setup MFA (proves it's enabled)
        await svc.register({"email": "default@example.com", "password": "password123", "name": "T"})
        user = await svc._user_repo.find_by_email("default@example.com")
        result = await svc.setup_mfa(user.id)
        assert "secret" in result
