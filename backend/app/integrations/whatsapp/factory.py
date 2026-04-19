"""Factory for WhatsApp BSP client."""
from app.core.config import settings
from app.integrations.whatsapp.base import WhatsAppClient
from app.integrations.whatsapp.gupshup import GupshupWhatsAppClient
from app.integrations.whatsapp.stub import StubWhatsAppClient


def get_whatsapp_client() -> WhatsAppClient:
    if settings.WHATSAPP_BSP == "gupshup":
        return GupshupWhatsAppClient()
    # TODO: wire Interakt/Karix/Twilio adapters here
    return StubWhatsAppClient()
