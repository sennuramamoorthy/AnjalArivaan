"""
GmailForwardAdapter — forwards a Gmail message to another address using the Gmail API.

Uses gmail.modify scope (minimum required per CLAUDE.md security rules).
Logs duration_ms on every outbound Google API call.
"""

import base64
import email as email_lib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

from .interface import IEmailForwardAdapter

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://www.googleapis.com/gmail/v1/users/me"


class GmailForwardAdapter(IEmailForwardAdapter):
    """
    Retrieves the original Gmail message and re-sends it as a forward
    using the Gmail send endpoint.
    """

    async def forward(
        self,
        original_mail_id: str,
        to_email: str,
        from_account_token: str,
        note: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {from_account_token}"}
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Step 1 — fetch original message (metadata + body)
                get_resp = await client.get(
                    f"{GMAIL_API_BASE}/messages/{original_mail_id}",
                    headers=headers,
                    params={"format": "full"},
                )
                get_resp.raise_for_status()
                msg_data = get_resp.json()

                original_subject = _extract_header(msg_data, "Subject")
                original_from = _extract_header(msg_data, "From")
                original_body = _extract_body(msg_data)

                # Step 2 — compose forward
                forward_body = (
                    f"{note}\n\n"
                    f"---------- Forwarded message ----------\n"
                    f"From: {original_from}\n"
                    f"Subject: {original_subject}\n\n"
                    f"{original_body}"
                )
                mime = MIMEText(forward_body, "plain")
                mime["To"] = to_email
                mime["Subject"] = f"Fwd: {original_subject}"
                raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

                # Step 3 — send
                send_resp = await client.post(
                    f"{GMAIL_API_BASE}/messages/send",
                    headers=headers,
                    json={"raw": raw},
                )
                send_resp.raise_for_status()

        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "Gmail forward failed",
                extra={
                    "duration_ms": duration_ms,
                    "original_mail_id": original_mail_id,
                    "to_email": to_email,
                    "error": str(exc),
                },
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Gmail message forwarded",
            extra={
                "duration_ms": duration_ms,
                "original_mail_id": original_mail_id,
                "to_email": to_email,
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_header(msg_data: dict, name: str) -> str:
    headers = msg_data.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_body(msg_data: dict) -> str:
    """Best-effort plain-text body extraction from Gmail payload."""
    payload = msg_data.get("payload", {})

    def _walk(part: dict) -> str:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        for sub in part.get("parts", []):
            result = _walk(sub)
            if result:
                return result
        return ""

    return _walk(payload) or "(no plain-text body)"
