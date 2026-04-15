from abc import ABC, abstractmethod
from typing import Optional

from src.modules.mail.domain.mail_message import MailMessage


class IMailRepository(ABC):
    @abstractmethod
    async def save(self, message: MailMessage) -> MailMessage:
        """Persist a MailMessage. Returns the saved (possibly updated) message."""
        ...

    @abstractmethod
    async def find_by_gmail_msg_id(
        self, gmail_msg_id: str, account_id: str
    ) -> Optional[MailMessage]:
        """
        Look up a message by its Gmail message ID scoped to an account.
        Returns None if not found.
        """
        ...

    @abstractmethod
    async def exists(self, gmail_msg_id: str, account_id: str) -> bool:
        """Return True if the message has already been synced."""
        ...

    @abstractmethod
    async def list_by_account(
        self,
        account_id: str,
        *,
        folder: str = "inbox",
        filter: str = "all",
        search: str = "",
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MailMessage], int]:
        """
        Return (messages, total_count) for the account.

        ``folder`` maps to a Gmail system label (``inbox``→INBOX,
        ``sent``→SENT, ``drafts``→DRAFT, ``trash``→TRASH,
        ``starred``→STARRED, ``important``→IMPORTANT). Use ``"all"`` to
        skip the folder filter.

        ``filter`` is an orthogonal cross-cut (urgent / unread / government)
        applied on top of the folder.
        """
        ...

    @abstractmethod
    async def find_by_id(self, mail_id: str, account_id: str) -> Optional[MailMessage]:
        """Fetch a single message by ID, scoped to account."""
        ...

    @abstractmethod
    async def find_thread(self, thread_id: str, account_id: str) -> list[MailMessage]:
        """Fetch all messages in a thread, ordered by received_at ASC."""
        ...

    @abstractmethod
    async def mark_read(self, mail_id: str, account_id: str) -> bool:
        """Mark a message as read. Returns True if updated, False if not found."""
        ...

    @abstractmethod
    async def mark_thread_read(self, thread_id: str, account_id: str) -> int:
        """Mark every message in a thread as read. Returns rows updated."""
        ...
