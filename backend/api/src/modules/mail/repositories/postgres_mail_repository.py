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

from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
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
                        "to_addresses": list(message.to_addresses or []),
                        "cc_addresses": list(message.cc_addresses or []),
                        "subject": message.subject,
                        "body_text": message.body_text,
                        "body_html": message.body_html,
                        "received_at": message.received_at,
                        "labels": list(message.labels or []),
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

    # Maps the folder slug used by the API/UI to the Gmail system label
    # value stored in mail_messages.labels (text[]).
    _FOLDER_TO_LABEL: dict[str, str] = {
        "inbox": "INBOX",
        "sent": "SENT",
        "drafts": "DRAFT",
        "trash": "TRASH",
        "starred": "STARRED",
        "important": "IMPORTANT",
    }

    async def list_by_account(
        self,
        account_id: str,
        *,
        folder: str = "inbox",
        filter: str = "all",
        search: str = "",
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MailMessage], int]:
        loop = asyncio.get_event_loop()
        with self._logger.timed(
            "postgres.list_by_account", account_id=account_id, folder=folder
        ):
            return await loop.run_in_executor(
                None,
                lambda: self._list_by_account_sync(
                    account_id, folder, filter, search, sort, page, page_size
                ),
            )

    def _list_by_account_sync(
        self,
        account_id: str,
        folder: str,
        filter: str,
        search: str,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[MailMessage], int]:
        where = "WHERE account_id = %s"
        params: list[Any] = [account_id]

        # Folder filter — maps to a Gmail label that must be present in
        # the labels[] column. `all` skips the folder constraint.
        label = self._FOLDER_TO_LABEL.get(folder.lower())
        if label is not None:
            where += " AND %s = ANY(labels)"
            params.append(label)
        # Trash is excluded by default unless explicitly requested, so
        # archived/deleted threads don't leak into Inbox/Important/etc.
        if folder.lower() != "trash":
            where += " AND NOT ('TRASH' = ANY(labels))"

        if filter == "urgent":
            where += " AND urgency_level IN ('HIGH', 'CRITICAL')"
        elif filter == "unread":
            where += " AND is_read = FALSE"
        elif filter == "government":
            # Double the % so psycopg2 doesn't treat them as param placeholders.
            where += " AND (from_address LIKE '%%.gov.in' OR from_address LIKE '%%.nic.in')"

        if search:
            pattern = f"%{search}%"
            where += " AND (subject ILIKE %s OR from_address ILIKE %s OR body_text ILIKE %s)"
            params.extend([pattern, pattern, pattern])

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS total FROM mail_messages {where}", params)
                total = cur.fetchone()["total"]

                # Whitelisted sort — never interpolate untrusted sort strings.
                order_by = {
                    "newest": "received_at DESC",
                    "oldest": "received_at ASC",
                    "sender": "LOWER(from_address) ASC, received_at DESC",
                    "subject": "LOWER(subject) ASC, received_at DESC",
                }.get((sort or "newest").lower(), "received_at DESC")

                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT * FROM mail_messages {where} ORDER BY {order_by} LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                rows = cur.fetchall()

        return [self._row_to_domain(row) for row in rows], total

    async def find_by_id(self, mail_id: str, account_id: str) -> Optional[MailMessage]:
        loop = asyncio.get_event_loop()
        with self._logger.timed("postgres.find_by_id", mail_id=mail_id):
            return await loop.run_in_executor(
                None, lambda: self._find_by_id_sync(mail_id, account_id)
            )

    def _find_by_id_sync(self, mail_id: str, account_id: str) -> Optional[MailMessage]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM mail_messages WHERE id = %s AND account_id = %s",
                    (mail_id, account_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_domain(row)

    async def find_thread(self, thread_id: str, account_id: str) -> list[MailMessage]:
        loop = asyncio.get_event_loop()
        with self._logger.timed("postgres.find_thread", thread_id=thread_id):
            return await loop.run_in_executor(
                None, lambda: self._find_thread_sync(thread_id, account_id)
            )

    def _find_thread_sync(self, thread_id: str, account_id: str) -> list[MailMessage]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM mail_messages WHERE thread_id = %s AND account_id = %s ORDER BY received_at ASC",
                    (thread_id, account_id),
                )
                rows = cur.fetchall()
                return [self._row_to_domain(row) for row in rows]

    async def mark_read(self, mail_id: str, account_id: str) -> bool:
        loop = asyncio.get_event_loop()
        with self._logger.timed("postgres.mark_read", mail_id=mail_id):
            return await loop.run_in_executor(
                None, lambda: self._mark_read_sync(mail_id, account_id)
            )

    def _mark_read_sync(self, mail_id: str, account_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mail_messages SET is_read = TRUE WHERE id = %s AND account_id = %s",
                    (mail_id, account_id),
                )
            conn.commit()
            return cur.rowcount > 0

    async def mark_thread_read(self, thread_id: str, account_id: str) -> int:
        loop = asyncio.get_event_loop()
        with self._logger.timed("postgres.mark_thread_read", thread_id=thread_id):
            return await loop.run_in_executor(
                None, lambda: self._mark_thread_read_sync(thread_id, account_id)
            )

    def _mark_thread_read_sync(self, thread_id: str, account_id: str) -> int:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mail_messages SET is_read = TRUE "
                    "WHERE thread_id = %s AND account_id = %s AND is_read = FALSE",
                    (thread_id, account_id),
                )
                conn.commit()
                return cur.rowcount

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
