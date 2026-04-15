"""
DbTokenAdapter (mail-side) — reads the Fernet-encrypted refresh token stored
inline in linked_accounts.vault_ref by the account_link module, exchanges it
with Google's token endpoint, and returns a short-lived access token.

Implements `mail.adapters.vault.interface.IVaultAdapter` so it's a drop-in
replacement for `HashiCorpVaultAdapter` in Phase 1 (no Vault dependency).

Caches access tokens in-process for ~50 minutes (Google issues 1h tokens) to
avoid hitting the token endpoint on every Gmail call.
"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from cryptography.fernet import Fernet

from src.modules.account_link.repositories.interface import ILinkedAccountRepository
from src.modules.mail.adapters.vault.interface import IVaultAdapter

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_TOKEN_TTL_SECONDS = 50 * 60  # refresh ~10 min before expiry


def _derive_fernet_key(encryption_key_hex: str) -> bytes:
    raw = bytes.fromhex(encryption_key_hex)[:32]
    return base64.urlsafe_b64encode(raw)


class DbTokenAdapter(IVaultAdapter):
    def __init__(
        self,
        *,
        linked_account_repo: ILinkedAccountRepository,
        encryption_key_hex: str,
        google_client_id: str,
        google_client_secret: str,
        logger: Any,
    ) -> None:
        self._repo = linked_account_repo
        self._fernet = Fernet(_derive_fernet_key(encryption_key_hex))
        self._client_id = google_client_id
        self._client_secret = google_client_secret
        self._logger = logger
        # account_id -> (access_token, expires_at_epoch)
        self._cache: dict[str, tuple[str, float]] = {}

    async def get_access_token(self, account_id: str) -> str:
        now = time.time()
        cached = self._cache.get(account_id)
        if cached and cached[1] > now:
            return cached[0]

        account = await self._repo.find_by_id(account_id)
        if account is None:
            raise ValueError(f"Linked account {account_id} not found")
        if not account.vault_ref or not account.vault_ref.startswith("enc:"):
            raise ValueError(
                f"Linked account {account_id} has no encrypted refresh token"
            )

        encrypted = account.vault_ref[len("enc:"):].encode("utf-8")
        try:
            refresh_token = self._fernet.decrypt(encrypted).decode("utf-8")
        except Exception as exc:
            self._logger.error(
                "vault.decrypt_failed", account_id=account_id, error=str(exc)
            )
            raise

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if resp.status_code != 200:
            self._logger.error(
                "vault.token_refresh_failed",
                account_id=account_id,
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()

        payload = resp.json()
        access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        ttl = min(expires_in - 60, _TOKEN_TTL_SECONDS)
        self._cache[account_id] = (access_token, now + ttl)
        return access_token
