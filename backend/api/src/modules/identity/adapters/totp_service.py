"""TOTP (Time-based One-Time Password) adapter — interface + implementations."""

import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pyotp


@dataclass
class TotpSecret:
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class ITotpService(ABC):
    @abstractmethod
    async def generate_secret(
        self, email: str, issuer: str = "AnjalArivaan"
    ) -> TotpSecret: ...

    @abstractmethod
    def verify(self, token: str, secret: str) -> bool: ...

    @abstractmethod
    def hash_backup_code(self, code: str) -> str: ...


class PyOTPTotpService(ITotpService):
    """Production TOTP using pyotp."""

    async def generate_secret(
        self, email: str, issuer: str = "AnjalArivaan"
    ) -> TotpSecret:
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=email, issuer_name=issuer)
        backup_codes = [secrets.token_hex(4) for _ in range(8)]
        return TotpSecret(secret=secret, qr_code_uri=uri, backup_codes=backup_codes)

    def verify(self, token: str, secret: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)

    def hash_backup_code(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()


class MockTotpService(ITotpService):
    """Test double — always generates predictable secrets."""

    VALID_CODE = "123456"

    async def generate_secret(
        self, email: str, issuer: str = "AnjalArivaan"
    ) -> TotpSecret:
        return TotpSecret(
            secret="MOCKSECRET",
            qr_code_uri=f"otpauth://totp/{issuer}:{email}?secret=MOCKSECRET",
            backup_codes=["backup1", "backup2", "backup3"],
        )

    def verify(self, token: str, secret: str) -> bool:
        return token == self.VALID_CODE

    def hash_backup_code(self, code: str) -> str:
        return f"hashed:{code}"
