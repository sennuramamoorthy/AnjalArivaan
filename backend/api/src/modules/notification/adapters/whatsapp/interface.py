from abc import ABC, abstractmethod


class IWhatsAppAdapter(ABC):
    @abstractmethod
    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        template_params: dict[str, str],
    ) -> dict:
        """
        Send a pre-approved WhatsApp template message.

        Returns {"message_id": "...", "status": "sent"}
        """
        ...
