"""MockVaultAdapter — returns pre-configured access tokens for tests."""

from .interface import IVaultAdapter


class MockVaultAdapter(IVaultAdapter):
    """
    In-memory Vault adapter.

    ``tokens`` maps account_id → access_token string.
    ``called_with_account_ids`` records every account_id passed to get_access_token.
    """

    def __init__(self, tokens: dict[str, str] | None = None) -> None:
        self.tokens: dict[str, str] = tokens or {}
        self.called_with_account_ids: list[str] = []

    async def get_access_token(self, account_id: str) -> str:
        self.called_with_account_ids.append(account_id)
        if account_id not in self.tokens:
            raise KeyError(f"MockVaultAdapter: no token for account_id={account_id!r}")
        return self.tokens[account_id]
