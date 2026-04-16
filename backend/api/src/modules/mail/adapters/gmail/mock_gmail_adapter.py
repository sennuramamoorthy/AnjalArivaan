"""MockGmailAdapter — returns configurable fake responses for tests."""

from typing import Any

from .interface import IGmailAdapter


class MockGmailAdapter(IGmailAdapter):
    """
    In-memory Gmail adapter for unit tests.

    Pass ``messages`` to preload the list returned by ``list_messages``.
    Individual messages are looked up by their ``id`` field.
    ``attachment_data`` maps ``(message_id, attachment_id)`` → ``bytes``.
    """

    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self._messages: list[dict[str, Any]] = messages or []
        # Map message_id → message dict for get_message
        self._message_map: dict[str, dict[str, Any]] = {
            m["id"]: m for m in self._messages
        }
        # Map (message_id, attachment_id) → raw bytes
        self.attachment_data: dict[tuple[str, str], bytes] = {}
        # Captures forward_message() calls for test assertions.
        self.forwarded: list[dict[str, Any]] = []

    async def list_messages(
        self,
        access_token: str,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        msgs = [{"id": m["id"], "threadId": m.get("threadId", "")} for m in self._messages]
        return {"messages": msgs, "resultSizeEstimate": len(msgs)}

    async def get_message(self, access_token: str, message_id: str) -> dict[str, Any]:
        if message_id not in self._message_map:
            raise ValueError(f"MockGmailAdapter: unknown message_id={message_id!r}")
        return self._message_map[message_id]

    async def get_attachment(
        self, access_token: str, message_id: str, attachment_id: str
    ) -> bytes:
        key = (message_id, attachment_id)
        if key not in self.attachment_data:
            return b""
        return self.attachment_data[key]

    async def get_history(
        self, access_token: str, start_history_id: str
    ) -> dict[str, Any]:
        return {"history": [], "historyId": start_history_id}

    async def setup_push_notifications(
        self, access_token: str, topic_name: str, label_ids: list[str]
    ) -> dict[str, Any]:
        return {"historyId": "1", "expiration": "9999999999999"}

    async def send_message(
        self,
        access_token: str,
        raw_rfc2822: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        return {"id": "mock-sent-1", "threadId": thread_id or "mock-thread-1"}

    async def forward_message(
        self,
        account_id: str,
        message_id: str,
        to_addresses: list[str],
    ) -> dict[str, Any]:
        self.forwarded.append(
            {
                "account_id": account_id,
                "message_id": message_id,
                "to_addresses": list(to_addresses),
            }
        )
        return {"id": "mock-forwarded-1", "status": "sent"}
