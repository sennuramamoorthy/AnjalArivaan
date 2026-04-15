"""InMemoryMailRepository — used in tests; checks duplicates by gmail_msg_id + account_id."""

from typing import Optional

from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from .interface import IMailRepository

_GOV_SUFFIXES = (".gov.in", ".nic.in")


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

    async def list_by_account(
        self,
        account_id: str,
        *,
        filter: str = "all",
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MailMessage], int]:
        # Collect all messages for this account
        msgs = [m for m in self._store.values() if m.account_id == account_id]

        # Apply filter
        if filter == "urgent":
            msgs = [m for m in msgs if m.urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)]
        elif filter == "unread":
            msgs = [m for m in msgs if not m.is_read]
        elif filter == "government":
            msgs = [m for m in msgs if any(m.from_address.endswith(s) for s in _GOV_SUFFIXES)]

        # Apply search
        if search:
            q = search.lower()
            msgs = [
                m for m in msgs
                if q in m.subject.lower()
                or q in m.from_address.lower()
                or q in m.body_text.lower()
            ]

        # Sort by received_at DESC
        msgs.sort(key=lambda m: m.received_at, reverse=True)
        total = len(msgs)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        return msgs[start:end], total

    async def find_by_id(self, mail_id: str, account_id: str) -> Optional[MailMessage]:
        for m in self._store.values():
            if m.id == mail_id and m.account_id == account_id:
                return m
        return None

    async def find_thread(self, thread_id: str, account_id: str) -> list[MailMessage]:
        msgs = [
            m for m in self._store.values()
            if m.thread_id == thread_id and m.account_id == account_id
        ]
        msgs.sort(key=lambda m: m.received_at)
        return msgs

    async def mark_read(self, mail_id: str, account_id: str) -> bool:
        msg = await self.find_by_id(mail_id, account_id)
        if msg is None:
            return False
        msg.is_read = True
        return True
