"""UrgencyOutboxWorker — polls urgency_outbox and dispatches both side effects.

Dispatch flow per row:
  1. Fetch unprocessed rows (oldest first).
  2. For each row:
       a. WhatsApp template send (skipped if no phone).
       b. Email forward to line-manager (skipped if no line-manager email).
       c. Audit log (append-only) via injected audit adapter.
       d. If at least one channel succeeded → mark row processed.
       e. If both channels failed → record failure, leave row for retry.
  3. Idempotency: ``mark_processed`` is a no-op on already-processed rows,
     and the WhatsApp adapter is called exactly once per row per invocation.

All errors from adapters are caught — one failing dispatch must NOT block
another row. Structured JSON log per CLAUDE.md carries:
  thread_id, account_id, user_id, line_manager_email,
  whatsapp_template, matched_rules, duration_ms, trace_id
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from src.modules.notification.adapters.email_forward.interface import IEmailForwardAdapter
from src.modules.urgency.adapters.whatsapp.interface import IWhatsAppAdapter
from src.modules.urgency.repositories.urgency_outbox_repo import (
    IUrgencyOutboxRepository,
    UrgencyOutboxRow,
)

logger = logging.getLogger(__name__)

AUDIT_ACTOR_SYSTEM = "system"
AUDIT_ACTION_URGENT_ESCALATED = "URGENT_ESCALATED"
DEEP_LINK_TEMPLATE = "https://app.takshashilauniv.ac.in/mail/{message_id}"


class UrgencyOutboxWorker:
    """Consumer half of the transactional outbox.

    All external I/O goes through adapter interfaces. Tests inject
    ``MockWhatsAppAdapter`` and ``MockEmailForwardAdapter``.
    """

    def __init__(
        self,
        outbox_repo: IUrgencyOutboxRepository,
        whatsapp_adapter: IWhatsAppAdapter,
        email_forward_adapter: IEmailForwardAdapter,
        audit_repo: Any = None,
        vault_adapter: Any = None,
        whatsapp_template_fallback: str = "urgent_gov_email_v1",
    ) -> None:
        self._repo = outbox_repo
        self._whatsapp = whatsapp_adapter
        self._email_forward = email_forward_adapter
        self._audit = audit_repo
        self._vault = vault_adapter
        self._fallback_template = whatsapp_template_fallback

    async def process_batch(self, batch_size: int = 25) -> int:
        rows = await self._repo.list_unprocessed(limit=batch_size)
        dispatched = 0
        for row in rows:
            if await self._dispatch_row(row):
                dispatched += 1
        return dispatched

    async def _dispatch_row(self, row: UrgencyOutboxRow) -> bool:
        trace_id = str(uuid.uuid4())
        t0 = time.monotonic()
        whatsapp_sent = False
        forwarded = False
        errors: list[str] = []

        template_name = row.whatsapp_template or self._fallback_template

        # --- WhatsApp --------------------------------------------------
        if row.whatsapp_phone:
            try:
                await self._whatsapp.send_template(
                    template_name=template_name,
                    to_phone=row.whatsapp_phone,
                    parameters={
                        "subject": row.reason[:120] if row.reason else "Urgent mail",
                        "deadline": row.detected_deadline or "Not specified",
                        "deep_link": DEEP_LINK_TEMPLATE.format(message_id=row.message_id),
                    },
                )
                whatsapp_sent = True
            except Exception as exc:  # noqa: BLE001
                errors.append(f"whatsapp: {exc}")

        # --- Email forward --------------------------------------------
        if row.line_manager_email:
            try:
                token = ""
                if self._vault is not None:
                    try:
                        token = await self._vault.get_access_token(row.account_id)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"vault: {exc}")
                note = (
                    f"[AnjalArivaan] Urgent government mail escalation. "
                    f"Matched rules: {', '.join(row.matched_rules) or 'n/a'}. "
                    f"Deadline: {row.detected_deadline or 'n/a'}."
                )
                await self._email_forward.forward(
                    original_mail_id=row.message_id,
                    to_email=row.line_manager_email,
                    from_account_token=token,
                    note=note,
                )
                forwarded = True
            except Exception as exc:  # noqa: BLE001
                errors.append(f"forward: {exc}")

        duration_ms = int((time.monotonic() - t0) * 1000)

        log_extra = {
            "service": "urgency.outbox_worker",
            "trace_id": trace_id,
            "thread_id": row.thread_id,
            "message_id": row.message_id,
            "account_id": row.account_id,
            "user_id": row.user_id,
            "line_manager_email": row.line_manager_email or "",
            "whatsapp_template": template_name,
            "matched_rules": row.matched_rules,
            "whatsapp_sent": whatsapp_sent,
            "forwarded": forwarded,
            "duration_ms": duration_ms,
        }

        any_success = whatsapp_sent or forwarded

        if any_success:
            logger.info("urgent_escalated", extra=log_extra)
            if self._audit is not None:
                try:
                    await self._audit.log_event(
                        actor=AUDIT_ACTOR_SYSTEM,
                        action=AUDIT_ACTION_URGENT_ESCALATED,
                        target=row.thread_id or row.message_id,
                        after={
                            "thread_id": row.thread_id,
                            "message_id": row.message_id,
                            "account_id": row.account_id,
                            "user_id": row.user_id,
                            "matched_rules": row.matched_rules,
                            "reason": row.reason,
                            "whatsapp_sent": whatsapp_sent,
                            "forwarded": forwarded,
                            "line_manager_email": row.line_manager_email,
                            "whatsapp_template": template_name,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    # Audit is best-effort — never block dispatch.
                    errors.append(f"audit: {exc}")
            await self._repo.mark_processed(row.id)
            if errors:
                await self._repo.record_failure(row.id, "; ".join(errors))
            return True

        # Nothing dispatched — record failure, leave for retry.
        err_text = "; ".join(errors) if errors else "no_channel_available"
        logger.warning(
            "urgent_escalation_failed",
            extra={**log_extra, "error": err_text},
        )
        await self._repo.record_failure(row.id, err_text)
        return False


# ---------------------------------------------------------------------------
# Default WhatsApp template name — exposed for callers composing rows.
# ---------------------------------------------------------------------------

DEFAULT_WHATSAPP_TEMPLATE = "urgent_gov_email_v1"
