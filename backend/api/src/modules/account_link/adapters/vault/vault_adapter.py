"""HashiCorpVaultAccountLinkAdapter — stores/revokes Google OAuth refresh tokens in Vault KV v2."""

import logging

import httpx

from src.modules.account_link.adapters.vault.interface import IAccountLinkVaultAdapter

logger = logging.getLogger(__name__)


class HashiCorpVaultAccountLinkAdapter(IAccountLinkVaultAdapter):
    """
    Uses Vault KV v2 secret engine to store Google OAuth refresh tokens.

    Path convention: secret/data/oauth/<account_id>
    """

    def __init__(self, vault_addr: str, vault_token: str) -> None:
        self._vault_addr = vault_addr.rstrip("/")
        self._vault_token = vault_token

    def _headers(self) -> dict[str, str]:
        return {"X-Vault-Token": self._vault_token}

    async def store_refresh_token(self, account_id: str, refresh_token: str) -> str:
        vault_path = f"secret/data/oauth/{account_id}"
        url = f"{self._vault_addr}/v1/{vault_path}"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"data": {"refresh_token": refresh_token}},
                timeout=10.0,
            )
            if resp.status_code not in (200, 204):
                logger.error(
                    "Vault store failed for %s: %d %s",
                    account_id, resp.status_code, resp.text,
                )
                resp.raise_for_status()

        vault_ref = f"vault:{vault_path}"
        logger.info("Stored refresh token in Vault: %s", vault_ref)
        return vault_ref

    async def revoke_refresh_token(self, vault_ref: str) -> None:
        # vault_ref = "vault:secret/data/oauth/<account_id>"
        vault_path = vault_ref.replace("vault:", "", 1)
        # KV v2 metadata delete path
        metadata_path = vault_path.replace("secret/data/", "secret/metadata/", 1)
        url = f"{self._vault_addr}/v1/{metadata_path}"

        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers(), timeout=10.0)
            if resp.status_code not in (200, 204):
                logger.warning(
                    "Vault revoke returned %d for %s: %s",
                    resp.status_code, vault_ref, resp.text,
                )
