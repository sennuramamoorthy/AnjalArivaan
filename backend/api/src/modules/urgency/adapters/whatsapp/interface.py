"""IWhatsAppAdapter — generic BSP-agnostic boundary.

Templates must be pre-approved by Meta, so the interface does NOT accept
free-form text. Implementations receive ``(template_name, to_phone, parameters)``
and are responsible for whatever BSP-specific request shape is needed.
"""

from abc import ABC, abstractmethod


class IWhatsAppAdapter(ABC):
    @abstractmethod
    async def send_template(
        self,
        *,
        template_name: str,
        to_phone: str,
        parameters: dict[str, str],
    ) -> dict:
        """Send a pre-approved WhatsApp template.

        Returns: ``{"message_id": str, "status": "sent"}``.
        Raises on transport / BSP errors — caller decides retry policy.
        """
        ...
