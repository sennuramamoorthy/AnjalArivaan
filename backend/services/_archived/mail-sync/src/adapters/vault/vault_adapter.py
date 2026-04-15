"""
HashiCorpVaultAdapter — real implementation.

Calls the token broker sidecar (account-link service) to exchange
a Vault transit-encrypted refresh token ref for a short-lived Google
OAuth access token. The actual Vault API is NOT called directly here
to maintain clean service boundaries.
"""

import httpx

from .interface import IVaultAdapter


class HashiCorpVaultAdapter(IVaultAdapter):
    """
    Delegates to the Account Link token broker over mTLS (inside the cluster).
    The broker holds the Vault client token and performs the exchange.
    """

    def __init__(self, broker_url: str, logger: object) -> None:
        self._broker_url = broker_url.rstrip("/")
        self._logger = logger  # type: ignore[assignment]

    async def get_access_token(self, account_id: str) -> str:
        with self._logger.timed(  # type: ignore[attr-defined]
            "vault.get_access_token", account_id=account_id
        ):
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._broker_url}/internal/token-exchange",
                    json={"account_id": account_id},
                    timeout=10.0,
                )
                resp.raise_for_status()
                return resp.json()["access_token"]
