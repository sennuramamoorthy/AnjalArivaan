"""SyncUrgencyHook — adapter between MailSyncService and the urgency outbox.

Invoked synchronously from ``MailSyncService.sync_message`` after the mail
has been persisted. Loads the user + role rules, runs detection, and
enqueues an ``urgency_outbox`` row if the verdict is urgent.

Kept narrow by design — no WhatsApp / Gmail-forward here; those happen in
the Celery worker, decoupled via the outbox.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from src.modules.notification.repositories.interface import IUrgencyRuleRepository
from src.modules.urgency.repositories.urgency_outbox_repo import (
    IUrgencyOutboxRepository,
    UrgencyOutboxRow,
)
from src.modules.urgency.services.detection_service import UrgencyDetectionService
from src.modules.urgency.services.outbox_worker import DEFAULT_WHATSAPP_TEMPLATE

logger = logging.getLogger(__name__)


class SyncUrgencyHook:
    def __init__(
        self,
        detection_service: UrgencyDetectionService,
        rule_repo: IUrgencyRuleRepository,
        outbox_repo: IUrgencyOutboxRepository,
        user_repo: Any,
        whatsapp_template: str = DEFAULT_WHATSAPP_TEMPLATE,
    ) -> None:
        self._detector = detection_service
        self._rule_repo = rule_repo
        self._outbox_repo = outbox_repo
        self._user_repo = user_repo
        self._whatsapp_template = whatsapp_template

    async def on_new_mail(
        self,
        *,
        mail: Any,
        account_id: str,
        user_id: str,
        trace_id: str,
    ) -> Optional[str]:
        """Return the enqueued urgency_outbox row id, or None if not urgent."""
        t0 = time.monotonic()

        user = await self._user_repo.get_user(user_id)
        role = _field(user, "role") or ""
        if not role:
            return None

        rules = await self._rule_repo.get_rules_for_role(role)
        message_dict = {
            "from_address": getattr(mail, "from_address", "") or "",
            "subject": getattr(mail, "subject", "") or "",
            "body_text": getattr(mail, "body_text", "") or "",
        }
        verdict = self._detector.detect(message_dict, rules)

        if not verdict.is_urgent:
            return None

        row = UrgencyOutboxRow(
            user_id=user_id,
            account_id=account_id,
            thread_id=getattr(mail, "thread_id", "") or "",
            message_id=getattr(mail, "id", "") or getattr(mail, "gmail_msg_id", "") or "",
            matched_rules=list(verdict.matched_rules),
            reason=verdict.reason,
            detected_deadline=verdict.detected_deadline,
            line_manager_email=_field(user, "line_manager_email"),
            whatsapp_phone=_field(user, "phone"),
            whatsapp_template=self._whatsapp_template,
        )
        await self._outbox_repo.enqueue(row)

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "urgency_outbox_enqueued",
            extra={
                "service": "urgency.sync_hook",
                "trace_id": trace_id,
                "thread_id": row.thread_id,
                "message_id": row.message_id,
                "account_id": account_id,
                "user_id": user_id,
                "line_manager_email": row.line_manager_email or "",
                "whatsapp_template": self._whatsapp_template,
                "matched_rules": row.matched_rules,
                "duration_ms": duration_ms,
            },
        )
        return row.id


def _field(record: Any, name: str) -> Any:
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)
