"""MockAccountLinkVaultAdapter — in-memory vault for tests."""

from src.modules.account_link.adapters.vault.interface import IAccountLinkVaultAdapter


class MockAccountLinkVaultAdapter(IAccountLinkVaultAdapter):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.store_calls: list[dict] = []
        self.revoke_calls: list[str] = []

    async def store_refresh_token(self, account_id: str, refresh_token: str) -> str:
        vault_ref = f"vault:secret/data/oauth/{account_id}"
        self._store[vault_ref] = refresh_token
        self.store_calls.append(
            {"account_id": account_id, "refresh_token": refresh_token}
        )
        return vault_ref

    async def revoke_refresh_token(self, vault_ref: str) -> None:
        self.revoke_calls.append(vault_ref)
        self._store.pop(vault_ref, None)
