from abc import ABC, abstractmethod


class IVaultAdapter(ABC):
    @abstractmethod
    async def get_access_token(self, account_id: str) -> str:
        """
        Call the token broker to exchange the Vault-stored refresh token ref
        for a short-lived Google OAuth access token.
        """
        ...
