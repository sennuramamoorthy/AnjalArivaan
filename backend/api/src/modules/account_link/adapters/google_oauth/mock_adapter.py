"""MockGoogleOAuthAdapter — returns pre-configured responses for tests."""

from src.modules.account_link.adapters.google_oauth.interface import IGoogleOAuthAdapter


class MockGoogleOAuthAdapter(IGoogleOAuthAdapter):
    """
    In-memory Google OAuth adapter for unit tests.

    Configurable via constructor params. Records calls for assertion.
    """

    def __init__(
        self,
        *,
        user_email: str = "user@takshashilauniv.ac.in",
        user_name: str = "Test User",
        user_picture: str = "https://example.com/photo.jpg",
        refresh_token: str = "mock-refresh-token",
        access_token: str = "mock-access-token",
    ) -> None:
        self._user_email = user_email
        self._user_name = user_name
        self._user_picture = user_picture
        self._refresh_token = refresh_token
        self._access_token = access_token

        self.build_auth_url_calls: list[dict] = []
        self.exchange_code_calls: list[dict] = []
        self.get_user_info_calls: list[str] = []
        self.revoke_token_calls: list[str] = []

    async def build_auth_url(
        self, redirect_uri: str, state: str, scopes: list[str]
    ) -> str:
        self.build_auth_url_calls.append(
            {"redirect_uri": redirect_uri, "state": state, "scopes": scopes}
        )
        params = f"redirect_uri={redirect_uri}&state={state}"
        return f"https://accounts.google.com/o/oauth2/auth?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        self.exchange_code_calls.append(
            {"code": code, "redirect_uri": redirect_uri}
        )
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_in": 3600,
        }

    async def get_user_info(self, access_token: str) -> dict:
        self.get_user_info_calls.append(access_token)
        return {
            "email": self._user_email,
            "name": self._user_name,
            "picture": self._user_picture,
        }

    async def revoke_token(self, token: str) -> None:
        self.revoke_token_calls.append(token)
