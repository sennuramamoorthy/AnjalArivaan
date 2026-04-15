"""
PostgresMailRepository — production implementation using psycopg2.

All blocking DB calls are executed via asyncio.run_in_executor.
"""

import asyncio
import json
import uuid
from typing import Any, Optional

import psycopg2  # type: ignore[import]
import psycopg2.extras  # type: ignore[import]

from src.domain.mail_message import MailMessage, UrgencyLevel
from .interface import IMailRepository


class PostgresMailRepository(IMailRepository):
    """
    Stores MailMessage records in the ``mail_messages`` Postgres table.
    """

    def __init__(self, conn_string: str, logger: Any) -> None:
        self._conn_string = conn_string
        self._logger = logger

    def _get_conn(self):
        return psycopg2.connect(self._conn_string, cursor_factory=psycopg2.extras.RealDictCursor)

    async def save(self, message: MailMessage) -> MailMessage:
        loop = asyncio.get_event_loop()
        with self._logger.timed("postgres.save_mail", mail_id=message.id):
            await loop.run_in_executor(None, lambda: self._save_sync(message))
        return message

    def _save_sync(self, message: MailMessage) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mail_messages (
                        id, account_id, gmail_msg_id, thread_id,
                        from_address, to_addresses, cc_addresses,
                        subject, body_text, body_html,
                        received_at, labels, has_attachment,
                        urgency_level, urgency_score, is_read
                    ) VALUES (
                        %(id)s, %(account_id)s, %(gmail_msg_id)s, %(thread_id)s,
                        %(from_address)s, %(to_addresses)s, %(cc_addresses)s,
                        %(subject)s, %(body_text)s, %(body_html)s,
                        %(received_at)s, %(labels)s, %(has_attachment)s,
                        %(urgency_level)s, %(urgency_score)s, %(is_read)s
                    )
                    ON CONFLICT (gmail_msg_id, account_id) DO NOTHING
                    """,
                    {
                        "id": message.id,
                        "account_id": message.account_id,
                        "gmail_msg_id": message.gmail_msg_id,
                        "thread_id": message.thread_id,
                        "from_address": message.from_address,
                        "to_addresses": json.dumps(message.to_addresses),
                        "cc_addresses": json.dumps(message.cc_addresses),
                        "subject": message.subject,
                        "body_text": message.body_text,
                        "body_html": message.body_html,
                        "received_at": message.received_at,
                        "labels": json.dumps(message.labels),
                        "has_attachment": message.has_attachment,
                        "urgency_level": message.urgency_level.value,
                        "urgency_score": message.urgency_score,
                        "is_read": message.is_read,
                    },
                )
            conn.commit()

    async def find_by_gmail_msg_id(
        self, gmail_msg_id: str, account_id: str
    ) -> Optional[MailMessage]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._find_sync(gmail_msg_id, account_id)
        )

    def _find_sync(self, gmail_msg_id: str, account_id: str) -> Optional[MailMessage]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM mail_messages WHERE gmail_msg_id = %s AND account_id = %s",
                    (gmail_msg_id, account_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_domain(row)

    async def exists(self, gmail_msg_id: str, account_id: str) -> bool:
        result = await self.find_by_gmail_msg_id(gmail_msg_id, account_id)
        return result is not None

    @staticmethod
    def _row_to_domain(row: dict[str, Any]) -> MailMessage:
        return MailMessage(
            id=row["id"],
            account_id=row["account_id"],
            gmail_msg_id=row["gmail_msg_id"],
            thread_id=row["thread_id"],
            from_address=row["from_address"],
            to_addresses=json.loads(row["to_addresses"]) if isinstance(row["to_addresses"], str) else row["to_addresses"],
            cc_addresses=json.loads(row["cc_addresses"]) if isinstance(row["cc_addresses"], str) else row["cc_addresses"],
            subject=row["subject"],
            body_text=row["body_text"],
            body_html=row["body_html"],
            received_at=row["received_at"],
            labels=json.loads(row["labels"]) if isinstance(row["labels"], str) else row["labels"],
            has_attachment=row["has_attachment"],
            urgency_level=UrgencyLevel(row["urgency_level"]),
            urgency_score=float(row["urgency_score"]),
            is_read=row["is_read"],
        )
