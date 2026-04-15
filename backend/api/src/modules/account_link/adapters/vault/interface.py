from abc import ABC, abstractmethod


class IAccountLinkVaultAdapter(ABC):
    @abstractmethod
    async def store_refresh_token(self, account_id: str, refresh_token: str) -> str:
        """
        Store a Google OAuth refresh token in Vault, transit-encrypted.

        Returns: vault_ref — an opaque reference to retrieve the token later.
        """
        ...

    @abstractmethod
    async def revoke_refresh_token(self, vault_ref: str) -> None:
        """Delete the stored refresh token from Vault."""
        ...
