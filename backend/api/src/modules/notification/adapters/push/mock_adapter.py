from typing import Any

from src.modules.notification.adapters.push.interface import IPushAdapter


class MockPushAdapter(IPushAdapter):
    """In-memory push adapter for unit tests.

    Captures every call so tests can assert on delivery.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.sent.append(
            {
                "user_id": user_id,
                "title": title,
                "body": body,
                "data": data or {},
            }
        )

    def clear(self) -> None:
        self.sent.clear()
