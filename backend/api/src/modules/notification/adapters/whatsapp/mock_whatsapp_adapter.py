import uuid
from .interface import IWhatsAppAdapter


class MockWhatsAppAdapter(IWhatsAppAdapter):
    """In-memory WhatsApp adapter for unit tests."""

    def __init__(self):
        self._sent: list[dict] = []

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        template_params: dict[str, str],
    ) -> dict:
        record = {
            "message_id": str(uuid.uuid4()),
            "to_phone": to_phone,
            "template_name": template_name,
            "template_params": template_params,
            "status": "sent",
        }
        self._sent.append(record)
        return {"message_id": record["message_id"], "status": "sent"}

    def get_sent_messages(self) -> list[dict]:
        return list(self._sent)

    def reset(self) -> None:
        self._sent.clear()
