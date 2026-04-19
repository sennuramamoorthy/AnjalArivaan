"""WhatsApp BSP port."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class WhatsAppSendResult:
    message_id: str
    status: str
    receipt: dict[str, Any]


class WhatsAppClient(Protocol):
    """Pre-approved template messaging over the WhatsApp Business API."""

    async def send_template(
        self,
        to_e164: str,
        template_id: str,
        variables: dict[str, str],
    ) -> WhatsAppSendResult: ...
