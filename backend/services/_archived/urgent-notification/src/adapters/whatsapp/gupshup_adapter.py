"""
GupshupWhatsAppAdapter — real BSP integration via httpx.

Logs duration_ms on every outbound call (CLAUDE.md logging requirement).
Template name: urgent_gov_email_v1 (pre-approved by Meta).
Template params: subject, sender, deadline, deep_link.
"""

import time
import logging
from typing import Any

import httpx

from src.adapters.whatsapp.interface import IWhatsAppAdapter

logger = logging.getLogger(__name__)

# Deep-link base for the PWA
DEEP_LINK_BASE = "https://app.takshashilauniv.ac.in/mail"


class GupshupWhatsAppAdapter(IWhatsAppAdapter):
    """Calls the Gupshup REST API to send template messages."""

    def __init__(self, api_key: str, app_id: str, base_url: str = "https://api.gupshup.io/sm/api/v1"):
        self._api_key = api_key
        self._app_id = app_id
        self._base_url = base_url.rstrip("/")

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        template_params: dict[str, str],
    ) -> dict:
        url = f"{self._base_url}/template/msg"
        payload = {
            "channel": "whatsapp",
            "source": self._app_id,
            "destination": to_phone,
            "src.name": self._app_id,
            "template": {
                "id": template_name,
                "params": list(template_params.values()),
            },
        }
        headers = {"apikey": self._api_key, "Content-Type": "application/json"}

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "Gupshup WhatsApp send failed",
                extra={
                    "duration_ms": duration_ms,
                    "to_phone": to_phone,
                    "template_name": template_name,
                    "error": str(exc),
                },
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        message_id = data.get("messageId", data.get("message", {}).get("id", "unknown"))
        logger.info(
            "Gupshup WhatsApp message sent",
            extra={
                "duration_ms": duration_ms,
                "to_phone": to_phone,
                "template_name": template_name,
                "message_id": message_id,
            },
        )
        return {"message_id": message_id, "status": "sent"}
