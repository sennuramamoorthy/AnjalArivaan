"""WhatsApp BSP integration (PRD §3.3, §11).

Supports multiple Indian BSPs (Gupshup / Interakt / Karix / Twilio) via a common
`WhatsAppClient` interface. In prod, template messages must be pre-approved by Meta.
"""
from app.integrations.whatsapp.base import WhatsAppClient, WhatsAppSendResult
from app.integrations.whatsapp.factory import get_whatsapp_client
from app.integrations.whatsapp.stub import StubWhatsAppClient

__all__ = ["WhatsAppClient", "WhatsAppSendResult", "StubWhatsAppClient", "get_whatsapp_client"]
