"""BspWhatsAppAdapter — generic HTTP WhatsApp BSP adapter.

Config is fed from env vars so swapping between Gupshup / Interakt / Karix /
Twilio is purely deploy-time. The wire format is the minimal intersection of
all four BSPs — POST JSON to ``WHATSAPP_BSP_URL`` with:

  {
    "template_name": "<pre-approved by Meta>",
    "to": "<E.164 phone>",
    "parameters": {<ordered template vars>}
  }

Auth: ``Authorization: Bearer <WHATSAPP_BSP_API_KEY>`` + ``apikey`` header
(Gupshup uses ``apikey``, Interakt uses ``Authorization``; sending both is
harmless).

Logs ``duration_ms`` on every outbound call per CLAUDE.md.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from src.modules.urgency.adapters.whatsapp.interface import IWhatsAppAdapter

logger = logging.getLogger(__name__)


class BspWhatsAppAdapter(IWhatsAppAdapter):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        default_template: str | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv("WHATSAPP_BSP_URL", "")).rstrip("/")
        self._api_key = api_key or os.getenv("WHATSAPP_BSP_API_KEY", "")
        self._default_template = default_template or os.getenv(
            "WHATSAPP_TEMPLATE_NAME", "urgent_gov_email_v1"
        )
        self._timeout = timeout_seconds
        self._client = http_client  # Optional injected client for tests.

    async def send_template(
        self,
        *,
        template_name: str,
        to_phone: str,
        parameters: dict[str, str],
    ) -> dict:
        if not self._base_url:
            raise RuntimeError(
                "BspWhatsAppAdapter not configured — set WHATSAPP_BSP_URL env var."
            )
        if not self._api_key:
            raise RuntimeError(
                "BspWhatsAppAdapter not configured — set WHATSAPP_BSP_API_KEY env var."
            )

        effective_template = template_name or self._default_template
        payload = {
            "template_name": effective_template,
            "to": to_phone,
            "parameters": parameters,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "apikey": self._api_key,
            "Content-Type": "application/json",
        }

        t0 = time.monotonic()
        try:
            client = self._client or httpx.AsyncClient(timeout=self._timeout)
            try:
                response = await client.post(self._base_url, json=payload, headers=headers)
                response.raise_for_status()
                data: dict[str, Any] = response.json() if response.content else {}
            finally:
                if self._client is None:
                    await client.aclose()
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "whatsapp_bsp_failed",
                extra={
                    "service": "urgency.whatsapp",
                    "duration_ms": duration_ms,
                    "to_phone": _redact_phone(to_phone),
                    "template_name": effective_template,
                    "error": str(exc),
                },
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        message_id = (
            data.get("message_id")
            or data.get("messageId")
            or (data.get("message") or {}).get("id")
            or "unknown"
        )
        logger.info(
            "whatsapp_bsp_sent",
            extra={
                "service": "urgency.whatsapp",
                "duration_ms": duration_ms,
                "to_phone": _redact_phone(to_phone),
                "template_name": effective_template,
                "message_id": message_id,
            },
        )
        return {"message_id": message_id, "status": "sent"}


def _redact_phone(phone: str) -> str:
    """Mask all but the last 4 digits — DPDP-friendly logging."""
    if not phone:
        return ""
    tail = phone[-4:]
    return f"***{tail}"


class MockWhatsAppAdapter(IWhatsAppAdapter):
    """In-memory adapter for unit tests, matching the generic interface."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail_next: bool = False

    async def send_template(
        self,
        *,
        template_name: str,
        to_phone: str,
        parameters: dict[str, str],
    ) -> dict:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("mock BSP failure")
        record = {
            "template_name": template_name,
            "to_phone": to_phone,
            "parameters": dict(parameters),
        }
        self.sent.append(record)
        return {"message_id": f"mock-{len(self.sent)}", "status": "sent"}

    def reset(self) -> None:
        self.sent.clear()
