"""Deterministic stub for tests / dev."""
from __future__ import annotations

from uuid import uuid4

from app.integrations.whatsapp.base import WhatsAppClient, WhatsAppSendResult


class StubWhatsAppClient(WhatsAppClient):
    """Records sent messages in-memory; tests assert on `self.sent`."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_template(
        self,
        to_e164: str,
        template_id: str,
        variables: dict[str, str],
    ) -> WhatsAppSendResult:
        msg_id = f"wa_stub_{uuid4().hex[:12]}"
        record = {
            "message_id": msg_id,
            "to": to_e164,
            "template_id": template_id,
            "variables": variables,
        }
        self.sent.append(record)
        return WhatsAppSendResult(message_id=msg_id, status="sent", receipt=record)
