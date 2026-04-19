"""Mail, attachment, urgency-rule repositories."""
from sqlalchemy import select

from app.domain.models.mail import Attachment, MailMessage, UrgencyRule
from app.repositories.base import AccountScopedRepository, BaseRepository


class MailMessageRepository(AccountScopedRepository[MailMessage]):
    model = MailMessage

    def get_by_gmail_id(self, gmail_msg_id: str) -> MailMessage | None:
        stmt = select(MailMessage).where(MailMessage.gmail_msg_id == gmail_msg_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_thread(self, account_id: int, thread_id: str) -> list[MailMessage]:
        stmt = (
            select(MailMessage)
            .where(MailMessage.owner_account_id == account_id)
            .where(MailMessage.thread_id == thread_id)
            .order_by(MailMessage.received_at)
        )
        return list(self.db.execute(stmt).scalars().all())


class AttachmentRepository(AccountScopedRepository[Attachment]):
    model = Attachment


class UrgencyRuleRepository(BaseRepository[UrgencyRule]):
    model = UrgencyRule

    def list_for_role(self, role_designation: str) -> list[UrgencyRule]:
        stmt = (
            select(UrgencyRule)
            .where(UrgencyRule.role_designation == role_designation)
            .where(UrgencyRule.enabled.is_(True))
            .order_by(UrgencyRule.priority)
        )
        return list(self.db.execute(stmt).scalars().all())
