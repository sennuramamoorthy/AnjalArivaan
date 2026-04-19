"""Google Workspace integrations (Gmail, Calendar, People, settings.basic)."""
from app.integrations.google.base import GoogleMailClient, GoogleCalendarClient
from app.integrations.google.stub import StubGoogleCalendarClient, StubGoogleMailClient

__all__ = [
    "GoogleMailClient",
    "GoogleCalendarClient",
    "StubGoogleMailClient",
    "StubGoogleCalendarClient",
]
