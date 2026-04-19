"""Mail sync and ingestion (PRD §3.2, §4.1)."""
from __future__ import annotations

from app.core.events import DomainEvent, Events, bus
from app.domain.models.mail import MailMessage
from app.domain.schemas.mail import MailIngestPayload
from app.repositories.mail import MailMessageRepository


class MailService:
    """Ingests Gmail push notifications and writes normalized records."""

    def __init__(self, mail_repo: MailMessageRepository) -> None:
        self.mail_repo = mail_repo

    async def ingest(self, account_id: int, payload: MailIngestPayload) -> MailMessage:
        existing = self.mail_repo.get_by_gmail_id(payload.gmail_msg_id)
        if existing:
            return existing  # idempotent (PRD §10.3)
        mail = MailMessage(
            owner_account_id=account_id,
            gmail_msg_id=payload.gmail_msg_id,
            thread_id=payload.thread_id,
            from_address=payload.from_address.lower(),
            to_addresses=[a.lower() for a in payload.to_addresses],
            cc_addresses=[a.lower() for a in payload.cc_addresses],
            subject=payload.subject,
            snippet=payload.snippet,
            body_text=payload.body_text,
            body_html=payload.body_html,
            received_at=payload.received_at,
            labels=payload.labels,
            has_attachment=payload.has_attachment,
        )
        self.mail_repo.add(mail)
        self.mail_repo.commit()
        await bus.publish(
            DomainEvent(
                name=Events.MAIL_RECEIVED,
                payload={"mail_id": mail.id, "from": mail.from_address, "subject": mail.subject},
                account_id=account_id,
            )
        )
        return mail

    def get_thread(self, account_id: int, thread_id: str) -> list[MailMessage]:
        return self.mail_repo.list_thread(account_id, thread_id)

    def list_inbox(
        self, account_id: int, limit: int = 50, offset: int = 0
    ) -> list[MailMessage]:
        return list(self.mail_repo.list_for_account(account_id, limit=limit, offset=offset))
