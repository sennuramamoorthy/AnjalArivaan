"""VaultAdapter — HashiCorp Vault KV v2 backed store for Google OAuth refresh tokens.

Satisfies D1 ("refresh tokens never in Postgres or env vars — always in Vault
via the token broker"). Each linked account gets its own KV v2 secret at
``secret/data/linked_accounts/{accountId}/refresh_token``.

All outbound Vault calls are wrapped with ``logger.timed(...)`` so every entry
carries ``duration_ms`` per the CLAUDE.md logging contract.
"""

from typing import Any

import hvac

from src.modules.account_link.adapters.vault.interface import (
    IAccountLinkVaultAdapter,
)


class VaultAdapter(IAccountLinkVaultAdapter):
    """Real Vault adapter using the ``hvac`` KV v2 API.

    The hvac client is synchronous; we expose an async-looking interface to
    match :class:`IAccountLinkVaultAdapter` and stay wire-compatible with a
    future async vault client without touching callers.
    """

    def __init__(
        self,
        vault_addr: str,
        vault_token: str,
        logger: Any,
        mount_point: str = "secret",
        path_prefix: str = "linked_accounts",
    ) -> None:
        self._logger = logger
        self._mount_point = mount_point
        self._path_prefix = path_prefix
        self._client = hvac.Client(url=vault_addr, token=vault_token)

    # ---- path helpers -------------------------------------------------

    def _secret_path(self, account_id: str) -> str:
        return f"{self._path_prefix}/{account_id}/refresh_token"

    def _vault_ref(self, account_id: str) -> str:
        return f"vault:{self._mount_point}/data/{self._secret_path(account_id)}"

    def _account_id_from_ref(self, vault_ref: str) -> str:
        # ref shape: vault:{mount}/data/{prefix}/{accountId}/refresh_token
        prefix = f"vault:{self._mount_point}/data/{self._path_prefix}/"
        if not vault_ref.startswith(prefix):
            raise ValueError(f"unrecognised vault_ref: {vault_ref}")
        tail = vault_ref[len(prefix):]
        # tail = "{accountId}/refresh_token"
        return tail.split("/", 1)[0]

    # ---- interface ----------------------------------------------------

    async def store_refresh_token(
        self, account_id: str, refresh_token: str
    ) -> str:
        path = self._secret_path(account_id)
        with self._logger.timed("vault.store_token", account_id=account_id):
            self._client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={"refresh_token": refresh_token},
                mount_point=self._mount_point,
            )
        return self._vault_ref(account_id)

    async def get_refresh_token(self, account_id: str) -> str | None:
        path = self._secret_path(account_id)
        with self._logger.timed("vault.get_token", account_id=account_id):
            try:
                resp = self._client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self._mount_point,
                    raise_on_deleted_version=True,
                )
            except hvac.exceptions.InvalidPath:
                return None
        return resp["data"]["data"].get("refresh_token")

    async def revoke_refresh_token(self, vault_ref: str) -> None:
        account_id = self._account_id_from_ref(vault_ref)
        await self.delete_refresh_token(account_id)

    async def delete_refresh_token(self, account_id: str) -> None:
        path = self._secret_path(account_id)
        with self._logger.timed("vault.delete_token", account_id=account_id):
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self._mount_point,
            )
