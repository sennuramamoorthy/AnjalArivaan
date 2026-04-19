"""Gupshup BSP adapter (one of the supported Indian BSPs — PRD §11)."""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.integrations.whatsapp.base import WhatsAppClient, WhatsAppSendResult


class GupshupWhatsAppClient(WhatsAppClient):
    def __init__(self, api_base: str | None = None, api_key: str | None = None) -> None:
        self.api_base = (api_base or settings.WHATSAPP_API_BASE).rstrip("/")
        self.api_key = api_key or settings.WHATSAPP_API_KEY

    async def send_template(
        self,
        to_e164: str,
        template_id: str,
        variables: dict[str, str],
    ) -> WhatsAppSendResult:
        payload = {
            "channel": "whatsapp",
            "destination": to_e164.lstrip("+"),
            "template": {"id": template_id, "params": list(variables.values())},
        }
        headers = {"apikey": self.api_key, "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.post(
                    f"{self.api_base}/wa/api/v1/template/msg", json=payload, headers=headers
                )
                r.raise_for_status()
            except httpx.HTTPError as e:
                raise IntegrationError(f"Gupshup error: {e}", code="wa_error") from e
        data = r.json()
        return WhatsAppSendResult(
            message_id=data.get("messageId", ""),
            status=data.get("status", "unknown"),
            receipt=data,
        )
