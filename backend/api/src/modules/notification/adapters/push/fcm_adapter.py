"""FCM HTTP v1 push adapter.

Structural implementation only — in dev mode (empty ``fcm_project_id``) the
adapter logs and returns without performing any network call so the wider
stack remains runnable without real FCM credentials.
"""

from typing import Any, Callable, Awaitable

import httpx

from src.infra.logger import Logger
from src.modules.notification.adapters.push.interface import IPushAdapter


DeviceTokenLookup = Callable[[str], Awaitable[list[str]]]


class FcmPushAdapter(IPushAdapter):
    def __init__(
        self,
        project_id: str,
        logger: Logger,
        device_token_lookup: DeviceTokenLookup,
        access_token_provider: Callable[[], Awaitable[str]] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._project_id = project_id
        self._logger = logger
        self._token_lookup = device_token_lookup
        self._access_token_provider = access_token_provider
        self._http = http_client

    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self._project_id:
            self._logger.info(
                "fcm.skip_no_project_id",
                user_id=user_id,
                title=title,
            )
            return

        tokens = await self._token_lookup(user_id)
        if not tokens:
            self._logger.info("fcm.no_device_tokens", user_id=user_id)
            return

        if self._access_token_provider is None:
            self._logger.warn(
                "fcm.no_access_token_provider",
                user_id=user_id,
            )
            return

        access_token = await self._access_token_provider()
        url = (
            f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        client = self._http or httpx.AsyncClient(timeout=10.0)
        owns_client = self._http is None
        try:
            import time

            for token in tokens:
                payload = {
                    "message": {
                        "token": token,
                        "notification": {"title": title, "body": body},
                        "data": {k: str(v) for k, v in (data or {}).items()},
                    }
                }
                t0 = time.perf_counter()
                resp = await client.post(url, headers=headers, json=payload)
                duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                self._logger.info(
                    "fcm.send",
                    user_id=user_id,
                    status_code=resp.status_code,
                    duration_ms=duration_ms,
                )
        finally:
            if owns_client:
                await client.aclose()
