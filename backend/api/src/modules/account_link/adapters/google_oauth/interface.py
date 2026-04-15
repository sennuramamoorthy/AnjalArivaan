from abc import ABC, abstractmethod


class IGoogleOAuthAdapter(ABC):
    @abstractmethod
    async def build_auth_url(
        self, redirect_uri: str, state: str, scopes: list[str]
    ) -> str:
        """Build the Google OAuth2 authorization URL."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """
        Exchange an authorization code for tokens.

        Returns: {access_token, refresh_token, expires_in}
        """
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> dict:
        """
        Fetch the authenticated user's profile.

        Returns: {email, name, picture}
        """
        ...

    @abstractmethod
    async def revoke_token(self, token: str) -> None:
        """Revoke an OAuth2 token (access or refresh)."""
        ...
