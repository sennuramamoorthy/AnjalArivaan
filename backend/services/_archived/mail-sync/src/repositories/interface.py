from abc import ABC, abstractmethod
from typing import Optional

from src.domain.mail_message import MailMessage


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
