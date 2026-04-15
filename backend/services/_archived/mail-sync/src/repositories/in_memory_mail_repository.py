"""InMemoryMailRepository — used in tests; checks duplicates by gmail_msg_id + account_id."""

from typing import Optional

from src.domain.mail_message import MailMessage
from .interface import IMailRepository


class InMemoryMailRepository(IMailRepository):
    """
    Thread-safe-enough (single-event-loop) in-memory store for unit tests.

    Keyed by (gmail_msg_id, account_id) to enforce per-account isolation.
    """

    def __init__(self) -> None:
        # (gmail_msg_id, account_id) → MailMessage
        self._store: dict[tuple[str, str], MailMessage] = {}

    async def save(self, message: MailMessage) -> MailMessage:
        key = (message.gmail_msg_id, message.account_id)
        self._store[key] = message
        return message

    async def find_by_gmail_msg_id(
        self, gmail_msg_id: str, account_id: str
    ) -> Optional[MailMessage]:
        return self._store.get((gmail_msg_id, account_id))

    async def exists(self, gmail_msg_id: str, account_id: str) -> bool:
        return (gmail_msg_id, account_id) in self._store
