"""
GmailAdapter — real implementation using google-api-python-client.

All calls are wrapped with duration_ms logging via the anjal logger.
"""

import base64
import time
from typing import Any

import httpx

from .interface import IGmailAdapter


_GMAIL_BASE = "https://www.googleapis.com/gmail/v1/users/me"


class GmailAdapter(IGmailAdapter):
    """
    Thin async wrapper around the Gmail REST API.

    Uses ``httpx`` for async HTTP so no blocking I/O enters the service layer.
    The ``google-api-python-client`` discovery approach is synchronous, so we
    call the REST endpoints directly instead.
    """

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    async def list_messages(
        self,
        access_token: str,
        max_results: int = 50,
        page_token: str | None = None,
        include_spam_trash: bool = True,
    ) -> dict[str, Any]:
        # Gmail's /messages endpoint excludes SPAM and TRASH by default, which
        # means Trash stays empty in the PWA even after a full sync. We flip
        # includeSpamTrash on so Trash gets populated; Spam ends up filtered
        # out later via the folder filter (it's a separate label).
        params: dict[str, Any] = {
            "maxResults": max_results,
            "includeSpamTrash": "true" if include_spam_trash else "false",
        }
        if page_token:
            params["pageToken"] = page_token

        with self._logger.timed("gmail.list_messages", max_results=max_results):
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GMAIL_BASE}/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()

    async def get_message(self, access_token: str, message_id: str) -> dict[str, Any]:
        with self._logger.timed("gmail.get_message", message_id=message_id):
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GMAIL_BASE}/messages/{message_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"format": "full"},
                )
                resp.raise_for_status()
                return resp.json()

    async def get_attachment(
        self, access_token: str, message_id: str, attachment_id: str
    ) -> bytes:
        with self._logger.timed(
            "gmail.get_attachment", message_id=message_id, attachment_id=attachment_id
        ):
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GMAIL_BASE}/messages/{message_id}/attachments/{attachment_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                data = resp.json().get("data", "")
                return base64.urlsafe_b64decode(data + "==")

    async def get_history(
        self, access_token: str, start_history_id: str
    ) -> dict[str, Any]:
        with self._logger.timed("gmail.get_history", start_history_id=start_history_id):
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GMAIL_BASE}/history",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"startHistoryId": start_history_id},
                )
                resp.raise_for_status()
                return resp.json()

    async def send_message(
        self,
        access_token: str,
        raw_rfc2822: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        # Gmail's send endpoint expects the raw RFC-2822 message base64url-encoded.
        raw_b64 = base64.urlsafe_b64encode(raw_rfc2822.encode("utf-8")).decode("ascii").rstrip("=")
        payload: dict[str, Any] = {"raw": raw_b64}
        if thread_id:
            payload["threadId"] = thread_id

        with self._logger.timed("gmail.send_message", thread_id=thread_id or ""):
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GMAIL_BASE}/messages/send",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()

    async def setup_push_notifications(
        self, access_token: str, topic_name: str, label_ids: list[str]
    ) -> dict[str, Any]:
        with self._logger.timed("gmail.setup_push_notifications", topic=topic_name):
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GMAIL_BASE}/watch",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"topicName": topic_name, "labelIds": label_ids},
                )
                resp.raise_for_status()
                return resp.json()
