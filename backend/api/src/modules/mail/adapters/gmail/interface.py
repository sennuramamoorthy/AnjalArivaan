from abc import ABC, abstractmethod
from typing import Any


# Design pattern: **Adapter** (ports & adapters / hexagonal) — IGmailAdapter is
# the port; GmailAdapter and MockGmailAdapter are interchangeable implementations.
class IGmailAdapter(ABC):
    @abstractmethod
    async def list_messages(
        self,
        access_token: str,
        max_results: int = 50,
        page_token: str | None = None,
        include_spam_trash: bool = True,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_message(self, access_token: str, message_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_attachment(
        self, access_token: str, message_id: str, attachment_id: str
    ) -> bytes: ...

    @abstractmethod
    async def get_history(
        self, access_token: str, start_history_id: str
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def setup_push_notifications(
        self, access_token: str, topic_name: str, label_ids: list[str]
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def send_message(
        self,
        access_token: str,
        raw_rfc2822: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an RFC-2822 message. If thread_id is provided, the message is
        attached to that thread (Gmail's reply semantics)."""
        ...

    @abstractmethod
    async def forward_message(
        self,
        account_id: str,
        message_id: str,
        to_addresses: list[str],
    ) -> dict[str, Any]:
        """
        Forward an existing Gmail message (identified by ``message_id`` on the
        linked account ``account_id``) to ``to_addresses``.

        Implementations resolve the account's Gmail access token via Vault
        before dispatching; callers do not pass tokens so the adapter is the
        sole token-handling surface.
        """
        ...
