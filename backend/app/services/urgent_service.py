"""Urgent-government-email detection + escalation (PRD §3.3, §4.1).

The flow:
  1. Rule engine evaluates the mail against admin-configured rules
     (sender domain, keyword, deadline regex, LLM urgency score).
  2. If any rule fires → dispatch WhatsApp template to recipient AND
     forward WhatsApp+email to the line manager.
  3. Every escalation is audit-logged.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import datetime

from app.core.events import DomainEvent, Events, bus
from app.domain.models.mail import MailMessage, UrgencyRule
from app.domain.models.notification import (
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)
from app.domain.models.user import AppUser
from app.integrations.whatsapp.base import WhatsAppClient
from app.repositories.mail import MailMessageRepository, UrgencyRuleRepository
from app.repositories.notification import NotificationRepository
from app.repositories.user import AppUserRepository


@dataclass
class UrgencyDecision:
    matched: bool
    rule_id: int | None
    deadline: str | None
    score: float
    reason: str


class UrgencyRuleEngine:
    """Pure function evaluator — no IO, fully testable."""

    @staticmethod
    def evaluate(mail: MailMessage, rules: list[UrgencyRule]) -> UrgencyDecision:
        """Return UrgencyDecision for the highest-priority matching rule."""
        for rule in sorted(rules, key=lambda r: r.priority):
            reasons: list[str] = []
            # ---- Sender allowlist (supports *.gov.in etc via fnmatch)
            if rule.sender_patterns:
                domain = mail.from_address.split("@")[-1].lower()
                if not any(
                    fnmatch.fnmatch(domain, p.lower()) or p.lower() in mail.from_address.lower()
                    for p in rule.sender_patterns
                ):
                    continue
                reasons.append(f"sender={domain}")

            # ---- Keyword patterns (OR; at least one must match)
            text_blob = f"{mail.subject}\n{mail.snippet}\n{mail.body_text}".lower()
            if rule.keyword_patterns and not any(
                kw.lower() in text_blob for kw in rule.keyword_patterns
            ):
                continue
            if rule.keyword_patterns:
                reasons.append(f"keywords_matched")

            # ---- Deadline regex
            deadline: str | None = None
            if rule.deadline_regex:
                m = re.search(rule.deadline_regex, text_blob, flags=re.I)
                if m:
                    deadline = m.group(m.lastindex) if m.groups() else m.group(0)
                    reasons.append(f"deadline={deadline}")

            return UrgencyDecision(
                matched=True,
                rule_id=rule.id,
                deadline=deadline,
                score=1.0,
                reason="; ".join(reasons) or "rule_match",
            )
        return UrgencyDecision(matched=False, rule_id=None, deadline=None, score=0.0, reason="no_match")


class UrgentNotificationService:
    """Coordinates rule evaluation, WhatsApp dispatch, and line-manager forward."""

    def __init__(
        self,
        *,
        mail_repo: MailMessageRepository,
        rule_repo: UrgencyRuleRepository,
        users: AppUserRepository,
        notifications: NotificationRepository,
        whatsapp: WhatsAppClient,
        engine: UrgencyRuleEngine | None = None,
    ) -> None:
        self.mail_repo = mail_repo
        self.rule_repo = rule_repo
        self.users = users
        self.notifications = notifications
        self.whatsapp = whatsapp
        self.engine = engine or UrgencyRuleEngine()

    async def evaluate_and_dispatch(self, mail: MailMessage, recipient: AppUser) -> UrgencyDecision:
        rules = self.rule_repo.list_for_role(recipient.designation or "")
        decision = self.engine.evaluate(mail, rules)
        if not decision.matched:
            return decision

        mail.is_urgent = True
        mail.urgency_score = decision.score
        self.mail_repo.commit()

        deep_link = f"anjalarivaan://mail/{mail.id}"
        template_vars = {
            "subject": mail.subject[:60],
            "from": mail.from_address,
            "deadline": decision.deadline or "unspecified",
            "link": deep_link,
        }

        # Notify the recipient
        if recipient.phone_e164:
            result = await self.whatsapp.send_template(
                to_e164=recipient.phone_e164,
                template_id="urgent_gov_whatsapp_v1",
                variables=template_vars,
            )
            self.notifications.add(
                NotificationEvent(
                    user_id=recipient.id,
                    channel=NotificationChannel.WHATSAPP,
                    template_id="urgent_gov_whatsapp_v1",
                    payload=template_vars,
                    status=NotificationStatus.SENT,
                    delivery_receipt=result.message_id,
                    sent_at=datetime.utcnow(),
                )
            )

        # Forward to line manager
        if recipient.reporting_to_id:
            lm = self.users.get(recipient.reporting_to_id)
            if lm and lm.phone_e164:
                await self.whatsapp.send_template(
                    to_e164=lm.phone_e164,
                    template_id="urgent_gov_forward_v1",
                    variables={**template_vars, "recipient_name": recipient.full_name or recipient.email},
                )
                self.notifications.add(
                    NotificationEvent(
                        user_id=lm.id,
                        channel=NotificationChannel.WHATSAPP,
                        template_id="urgent_gov_forward_v1",
                        payload=template_vars,
                        status=NotificationStatus.SENT,
                        sent_at=datetime.utcnow(),
                    )
                )

        self.notifications.commit()
        await bus.publish(
            DomainEvent(
                name=Events.MAIL_URGENT_DETECTED,
                payload={"mail_id": mail.id, "rule_id": decision.rule_id, "reason": decision.reason},
                account_id=mail.owner_account_id,
            )
        )
        return decision
