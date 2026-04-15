"""GoogleOAuthAdapter — real implementation using httpx against Google OAuth2 endpoints."""

import logging
from urllib.parse import urlencode

import httpx

from src.modules.account_link.adapters.google_oauth.interface import IGoogleOAuthAdapter

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


class GoogleOAuthAdapter(IGoogleOAuthAdapter):
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def build_auth_url(
        self, redirect_uri: str, state: str, scopes: list[str]
    ) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 3600),
        }

    async def get_user_info(self, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "email": data["email"],
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
        }

    async def revoke_token(self, token: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GOOGLE_REVOKE_URL,
                params={"token": token},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Google token revocation returned %d: %s",
                    resp.status_code,
                    resp.text,
                )
