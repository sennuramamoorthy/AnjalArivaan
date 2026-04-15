"""
MailEventHandler — processes mail.new events from the outbox poller.

process_message() is pure / testable without any infrastructure dependency.
It validates the event dict and delegates to UrgencyNotificationService.
"""

import logging

from src.modules.notification.services.notification_service import UrgencyNotificationService

logger = logging.getLogger(__name__)

EXPECTED_EVENT_TYPE = "mail.new"

# Required keys for a valid mail.new event
_REQUIRED_KEYS = {"event_type", "account_id", "user_id", "mail"}


class MailEventHandler:
    def __init__(self, notification_service: UrgencyNotificationService):
        self._notification_service = notification_service

    async def process_message(self, event: dict) -> None:
        """
        Process a single decoded event dict.

        Testable without infrastructure — accepts a plain dict.
        Silently ignores unknown event types.
        Logs and swallows malformed events (no crash).
        """
        event_type = event.get("event_type")

        if event_type != EXPECTED_EVENT_TYPE:
            if event_type:
                logger.debug(
                    "Ignoring event with unknown type",
                    extra={"event_type": event_type},
                )
            return

        # Validate required keys before delegating
        missing = _REQUIRED_KEYS - event.keys()
        if missing or not isinstance(event.get("mail"), dict) or not event["mail"].get("id"):
            logger.warning(
                "Malformed mail.new event received; skipping",
                extra={"missing_keys": list(missing), "event_keys": list(event.keys())},
            )
            return

        trace_id: str = event.get("trace_id", "")

        try:
            await self._notification_service.process_new_mail(
                mail=event["mail"],
                account_id=event["account_id"],
                user_id=event["user_id"],
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.error(
                "Unhandled error processing mail.new event",
                extra={
                    "mail_id": event["mail"].get("id"),
                    "account_id": event.get("account_id"),
                    "trace_id": trace_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
