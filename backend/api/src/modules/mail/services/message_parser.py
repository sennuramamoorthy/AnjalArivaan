"""
GmailMessageParser — converts raw Gmail API message dicts into domain objects.

Handles MIME types: text/plain, text/html, multipart/mixed, multipart/alternative.
"""

import base64
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from src.modules.mail.domain.attachment import Attachment
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel


class GmailMessageParser:
    """
    Stateless parser.  Call ``parse(raw_message, account_id)`` to get a
    ``(MailMessage, list[Attachment])`` tuple.
    """

    def parse(
        self, raw_message: dict[str, Any], account_id: str
    ) -> tuple[MailMessage, list[Attachment]]:
        """Parse a raw Gmail API message dict into domain objects."""
        payload = raw_message.get("payload", {})
        headers = payload.get("headers", [])

        gmail_msg_id = raw_message["id"]
        mail_id = str(uuid.uuid4())

        from_address = self._get_header(headers, "From")
        to_raw = self._get_header(headers, "To")
        cc_raw = self._get_header(headers, "Cc")
        subject = self._get_header(headers, "Subject")

        to_addresses = self._split_addresses(to_raw)
        cc_addresses = self._split_addresses(cc_raw)

        # Prefer internalDate (epoch ms) over Date header
        internal_date_ms = raw_message.get("internalDate")
        if internal_date_ms:
            received_at = datetime.fromtimestamp(
                int(internal_date_ms) / 1000.0, tz=timezone.utc
            )
        else:
            date_str = self._get_header(headers, "Date")
            try:
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                received_at = datetime.now(timezone.utc)

        body_text, body_html = self._decode_body(payload)
        attachments = self._extract_attachments(payload, mail_id)

        message = MailMessage(
            id=mail_id,
            account_id=account_id,
            gmail_msg_id=gmail_msg_id,
            thread_id=raw_message.get("threadId", ""),
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            labels=raw_message.get("labelIds", []),
            has_attachment=len(attachments) > 0,
        )
        return message, attachments

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_header(self, headers: list[dict], name: str) -> str:
        """Case-insensitive header lookup. Returns empty string if not found."""
        name_lower = name.lower()
        for h in headers:
            if h.get("name", "").lower() == name_lower:
                return h.get("value", "")
        return ""

    def _split_addresses(self, raw: str) -> list[str]:
        """Split a comma-separated address header into a list, stripping whitespace."""
        if not raw:
            return []
        return [addr.strip() for addr in raw.split(",") if addr.strip()]

    def _decode_body(self, payload: dict[str, Any]) -> tuple[str, str]:
        """
        Recursively walk the MIME tree and return (text_body, html_body).

        Handles:
        - text/plain  → text_body
        - text/html   → html_body
        - multipart/alternative, multipart/mixed → recurse into parts
        """
        mime = payload.get("mimeType", "")

        if mime == "text/plain":
            return self._decode_part_body(payload), ""

        if mime == "text/html":
            return "", self._decode_part_body(payload)

        if mime.startswith("multipart/"):
            text_parts: list[str] = []
            html_parts: list[str] = []
            for part in payload.get("parts", []):
                t, h = self._decode_body(part)
                if t:
                    text_parts.append(t)
                if h:
                    html_parts.append(h)
            return "\n".join(text_parts), "\n".join(html_parts)

        # Unknown or message/* etc. — try body data as text fallback
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace"), ""
            except Exception:
                return "", ""
        return "", ""

    def _decode_part_body(self, part: dict[str, Any]) -> str:
        """Decode the base64url body.data of a single MIME part."""
        data = part.get("body", {}).get("data", "")
        if not data:
            return ""
        try:
            decoded = base64.urlsafe_b64decode(data + "==")
            return decoded.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _extract_attachments(
        self, payload: dict[str, Any], mail_id: str
    ) -> list[Attachment]:
        """
        Recursively find attachment parts in the MIME tree.

        A part is an attachment if it has a non-empty ``filename`` and an
        ``attachmentId`` in its body (meaning the data is separate from the
        message body and must be fetched via the attachments endpoint).
        """
        attachments: list[Attachment] = []
        self._walk_for_attachments(payload, mail_id, attachments)
        return attachments

    def _walk_for_attachments(
        self, part: dict[str, Any], mail_id: str, result: list[Attachment]
    ) -> None:
        filename = part.get("filename", "")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId", "")

        if filename and attachment_id:
            result.append(
                Attachment(
                    id=str(uuid.uuid4()),
                    mail_id=mail_id,
                    filename=filename,
                    mime_type=part.get("mimeType", "application/octet-stream"),
                    size_bytes=body.get("size", 0),
                    gmail_attachment_id=attachment_id,
                )
            )

        for sub_part in part.get("parts", []):
            self._walk_for_attachments(sub_part, mail_id, result)
