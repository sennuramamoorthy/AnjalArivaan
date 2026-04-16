"""
MailEventHandler — processes mail.new events from the outbox poller.

Two entry points:

1. ``process_message(event: dict)``
   Legacy-style entry used by the outbox poller. Validates a raw dict and
   delegates to :class:`UrgencyNotificationService` which carries the full
   rule-loading / dispatch / event-publish flow.

2. ``handle_new_mail(event: NewMailEvent)``
   Self-contained urgency-escalation flow. Evaluates urgency via an
   injected rule engine, then fans out to the WhatsApp adapter and the
   Gmail forward adapter in parallel-independent fashion (one adapter
   failing must not block the other). Used by newer callers that already
   hold a :class:`NewMailEvent`. Returns a :class:`HandlerResult` the
   caller can log / assert against.

Both paths live in the same class so the outbox poller registration in
``app.py`` does not need to change.

D16 note: when ``handle_new_mail`` is invoked from an HTTP context rather
than the background outbox consumer, the caller MUST verify that
``event.account_id`` belongs to ``event.user_id`` before enqueueing so that
a user's other linked accounts are never touched for a message they do not
own. Background callers (outbox poller) can rely on the producer because
mail sync already joined on ``linked_account``.

Logging contract (CLAUDE.md):
  Structured JSON fields required on every escalation log:
    service, trace_id, message_id, urgency_level,
    whatsapp_sent, forwarded, duration_ms
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.modules.notification.domain.events import NewMailEvent
from src.modules.notification.domain.urgency_result import UrgencyLevel
from src.modules.notification.services.notification_service import UrgencyNotificationService

logger = logging.getLogger(__name__)

EXPECTED_EVENT_TYPE = "mail.new"

# Required keys for a valid mail.new event dict (legacy process_message path)
_REQUIRED_KEYS = {"event_type", "account_id", "user_id", "mail"}

SERVICE_NAME = "mail-event-handler"
WHATSAPP_TEMPLATE = "urgent_gov_email_v1"
AUDIT_ACTION_ESCALATED = "URGENT_MAIL_ESCALATED"
AUDIT_ACTOR_SYSTEM = "system"


@dataclass
class HandlerResult:
    urgency_level: UrgencyLevel
    whatsapp_sent: bool = False
    forwarded: bool = False
    error: Optional[str] = None


class MailEventHandler:
    """
    Mail event consumer.

    Constructor accepts *either*:
      - ``notification_service`` (legacy — drives ``process_message``), or
      - the direct-dependency bundle
        (``rule_engine``, ``whatsapp_adapter``, ``gmail_adapter``, ``user_repo``,
         optional ``audit_repo``, optional ``logger``) — drives
        ``handle_new_mail``.

    Passing both is allowed (production wiring).
    """

    def __init__(
        self,
        notification_service: Optional[UrgencyNotificationService] = None,
        *,
        rule_engine: Any = None,
        whatsapp_adapter: Any = None,
        gmail_adapter: Any = None,
        user_repo: Any = None,
        audit_repo: Any = None,
        logger: Any = None,
    ) -> None:
        self._notification_service = notification_service
        self._rule_engine = rule_engine
        self._whatsapp = whatsapp_adapter
        self._gmail = gmail_adapter
        self._user_repo = user_repo
        self._audit_repo = audit_repo
        self._logger = logger

    # ------------------------------------------------------------------
    # Legacy dict-driven entry (used by outbox poller)
    # ------------------------------------------------------------------

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

        if self._notification_service is None:
            logger.warning(
                "mail.new event received but no notification_service is wired; skipping",
                extra={"trace_id": trace_id, "mail_id": event["mail"].get("id")},
            )
            return

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

    # ------------------------------------------------------------------
    # Direct-DI entry — NewMailEvent → escalation fan-out
    # ------------------------------------------------------------------

    async def handle_new_mail(self, event: NewMailEvent) -> HandlerResult:
        """
        Evaluate urgency for a :class:`NewMailEvent` and fan out notifications.

        Escalation fires only for HIGH or CRITICAL levels. WhatsApp and
        line-manager forwarding are independent: a failure in one must not
        block the other. Both failures collapse into the returned
        ``HandlerResult.error`` string (semicolon-joined).
        """
        if self._rule_engine is None:
            raise RuntimeError(
                "MailEventHandler.handle_new_mail called but rule_engine is not wired"
            )

        t0 = time.monotonic()

        decision = self._rule_engine.evaluate(event)
        level: UrgencyLevel = decision.level

        whatsapp_sent = False
        forwarded = False
        errors: list[str] = []

        if level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL):
            user = None
            if self._user_repo is not None:
                try:
                    user = await self._user_repo.get_user(event.user_id)
                except Exception as exc:  # pragma: no cover — defensive
                    errors.append(f"user_lookup: {exc}")

            phone = _field(user, "phone")
            line_manager_id = _field(user, "line_manager_id")

            # --- WhatsApp fan-out (adapter errors captured, not raised) ---
            if phone and self._whatsapp is not None:
                try:
                    await self._whatsapp.send_urgency_notification(
                        phone,
                        event.subject,
                        decision.reason,
                        event.trace_id,
                    )
                    whatsapp_sent = True
                except Exception as exc:
                    errors.append(f"whatsapp: {exc}")

            # --- Gmail forward to line manager (independent of WhatsApp) ---
            manager_email: Optional[str] = None
            if line_manager_id and self._user_repo is not None:
                try:
                    manager = await self._user_repo.get_user(line_manager_id)
                    manager_email = _field(manager, "email")
                except Exception as exc:
                    errors.append(f"manager_lookup: {exc}")

            if manager_email and self._gmail is not None:
                try:
                    await self._gmail.forward_message(
                        event.account_id,
                        event.message_id,
                        [manager_email],
                    )
                    forwarded = True
                except Exception as exc:
                    errors.append(f"forward: {exc}")

            # --- Audit trail (best-effort, never blocks) -----------------
            if (whatsapp_sent or forwarded) and self._audit_repo is not None:
                try:
                    await self._audit_repo.log_event(
                        actor=AUDIT_ACTOR_SYSTEM,
                        action=AUDIT_ACTION_ESCALATED,
                        target=event.message_id,
                        after={
                            "urgency_level": level.value,
                            "matched_rule": decision.matched_rule,
                            "reason": decision.reason,
                            "whatsapp_sent": whatsapp_sent,
                            "forwarded": forwarded,
                            "user_id": event.user_id,
                            "account_id": event.account_id,
                        },
                    )
                except Exception as exc:
                    errors.append(f"audit: {exc}")

        duration_ms = int((time.monotonic() - t0) * 1000)

        log_extra = {
            "service": SERVICE_NAME,
            "trace_id": event.trace_id,
            "message_id": event.message_id,
            "urgency_level": level.value,
            "whatsapp_sent": whatsapp_sent,
            "forwarded": forwarded,
            "duration_ms": duration_ms,
        }

        log = self._logger if self._logger is not None else logger

        if level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL):
            log.info("urgent_mail_escalated", extra=log_extra)
        else:
            log.info("mail_urgency_skipped", extra=log_extra)

        error_str = "; ".join(errors) if errors else None
        return HandlerResult(
            urgency_level=level,
            whatsapp_sent=whatsapp_sent,
            forwarded=forwarded,
            error=error_str,
        )


def _field(record: Any, name: str) -> Any:
    """
    Fetch ``name`` from either a dict or an object, so the handler works
    against both the dict-shaped :class:`IUserRepository` and object-shaped
    identity.User / test stubs.
    """
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)
