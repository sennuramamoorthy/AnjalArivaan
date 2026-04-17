from abc import ABC, abstractmethod
from typing import Any


class IPushAdapter(ABC):
    """Port for delivering push notifications (FCM/APNs)."""

    @abstractmethod
    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send a push notification.

        Args:
            user_id: Target AppUser id (used to look up device tokens).
            title: Notification title.
            body: Notification body.
            data: Optional structured payload delivered to the client.
        """
        ...
