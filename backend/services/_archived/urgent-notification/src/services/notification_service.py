"""
UrgencyNotificationService — orchestrates rule evaluation and dispatch.

Flow per new mail:
  1. Load user + role + line-manager info
  2. Load urgency rules for that role
  3. Evaluate rules via UrgencyRuleEngine (pure, no I/O)
  4. If urgent:
       a. Send WhatsApp to recipient (if phone present)
       b. Forward email to line manager (if reporting_to_email present)
       c. Publish mail.urgency_detected event to Kafka
  5. Emit a structured log entry with duration_ms

Logging contract (CLAUDE.md):
  Every AI/external call must log duration_ms.
  The urgency notification log must include:
    mail_id, account_id, urgency_level, urgency_score,
    matched_rule_id, whatsapp_sent, email_forwarded, duration_ms
"""

import logging
import time

from src.adapters.email_forward.interface import IEmailForwardAdapter
from src.adapters.messaging.interface import IMessageBus
from src.adapters.whatsapp.interface import IWhatsAppAdapter
from src.domain.events import UrgencyDetectedEvent
from src.domain.urgency_result import UrgencyLevel, UrgencyResult
from src.repositories.interface import IUrgencyRuleRepository, IUserRepository
from src.services.rule_engine import UrgencyRuleEngine

logger = logging.getLogger(__name__)

WHATSAPP_TEMPLATE = "urgent_gov_email_v1"
MAIL_DEEP_LINK = "https://app.takshashilauniv.ac.in/mail/{mail_id}"
URGENCY_TOPIC = "mail-events"


class UrgencyNotificationService:
    def __init__(
        self,
        rule_repo: IUrgencyRuleRepository,
        user_repo: IUserRepository,
        rule_engine: UrgencyRuleEngine,
        whatsapp_adapter: IWhatsAppAdapter,
        email_forward_adapter: IEmailForwardAdapter,
        message_bus: IMessageBus,
    ):
        self._rule_repo = rule_repo
        self._user_repo = user_repo
        self._rule_engine = rule_engine
        self._whatsapp = whatsapp_adapter
        self._email_forward = email_forward_adapter
        self._message_bus = message_bus

    async def process_new_mail(
        self,
        mail: dict,
        account_id: str,
        user_id: str,
        trace_id: str,
    ) -> UrgencyResult:
        """
        Evaluate urgency for a new mail event and dispatch notifications.

        Returns the UrgencyResult for the caller / consumer to log.
        """
        t0 = time.monotonic()
        mail_id: str = mail.get("id", "")

        # 1. Load user
        user = await self._user_repo.get_user(user_id)
        if user is None:
            logger.warning(
                "User not found; skipping urgency check",
                extra={"user_id": user_id, "mail_id": mail_id, "trace_id": trace_id, "duration_ms": 0},
            )
            return UrgencyResult(is_urgent=False, level=UrgencyLevel.NONE, score=0.0)

        role: str = user.get("role", "")
        phone: str | None = user.get("phone")
        line_manager_email: str | None = user.get("reporting_to_email")
        gmail_token: str = user.get("gmail_token", "")

        # 2. Load rules
        rules = await self._rule_repo.get_rules_for_role(role)

        # 3. Evaluate
        result = self._rule_engine.evaluate(mail, rules)

        if not result.is_urgent:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "Mail not urgent; no notification dispatched",
                extra={
                    "duration_ms": duration_ms,
                    "mail_id": mail_id,
                    "account_id": account_id,
                    "trace_id": trace_id,
                    "urgency_level": result.level.value,
                    "urgency_score": result.score,
                },
            )
            return result

        # 4a. WhatsApp
        whatsapp_sent = False
        if phone:
            deep_link = MAIL_DEEP_LINK.format(mail_id=mail_id)
            template_params = {
                "subject": mail.get("subject", ""),
                "sender": mail.get("from_address", ""),
                "deadline": result.detected_deadline or "Not specified",
                "deep_link": deep_link,
            }
            await self._whatsapp.send_template_message(
                to_phone=phone,
                template_name=WHATSAPP_TEMPLATE,
                template_params=template_params,
            )
            whatsapp_sent = True
        else:
            logger.warning(
                "No phone number for user; skipping WhatsApp notification",
                extra={"user_id": user_id, "mail_id": mail_id, "trace_id": trace_id},
            )

        # 4b. Email forward to line manager
        email_forwarded = False
        if line_manager_email:
            note = (
                f"[AnjalArivaan] Urgent government email detected.\n"
                f"Urgency level: {result.level.value} (score: {result.score:.1f})\n"
                f"Matched rule: {result.matched_rule_id}\n"
                f"Detected deadline: {result.detected_deadline or 'Not specified'}"
            )
            await self._email_forward.forward(
                original_mail_id=mail_id,
                to_email=line_manager_email,
                from_account_token=gmail_token,
                note=note,
            )
            email_forwarded = True
        else:
            logger.warning(
                "No line manager configured for user; skipping email forward",
                extra={"user_id": user_id, "mail_id": mail_id, "trace_id": trace_id},
            )

        # 4c. Publish event
        event = UrgencyDetectedEvent(
            account_id=account_id,
            user_id=user_id,
            trace_id=trace_id,
            mail_id=mail_id,
            urgency_level=result.level.value,
            urgency_score=result.score,
            rule_id=result.matched_rule_id or "",
            detected_deadline=result.detected_deadline,
            recipient_phone=phone or "",
            line_manager_email=line_manager_email or "",
        )
        await self._message_bus.publish(URGENCY_TOPIC, event.to_dict())

        # 5. Log with duration_ms
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Urgency notification dispatched",
            extra={
                "duration_ms": duration_ms,
                "mail_id": mail_id,
                "account_id": account_id,
                "trace_id": trace_id,
                "urgency_level": result.level.value,
                "urgency_score": result.score,
                "matched_rule_id": result.matched_rule_id,
                "whatsapp_sent": whatsapp_sent,
                "email_forwarded": email_forwarded,
            },
        )

        return result
