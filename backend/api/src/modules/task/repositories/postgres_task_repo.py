"""PostgreSQL task repository.

Reads/writes the ``tasks`` table as defined by the Prisma schema. Columns:
``id, assigner_id, assignee_id, subject, description, due_at, status,
source_mail_id, reply_token, created_at, updated_at``. ``status`` is a
Postgres enum type (``TaskStatus``) — string values are cast with
``::"TaskStatus"``.

Read paths degrade gracefully (empty + warn log) when the table is missing
so the daily briefing still renders in environments where migrations have
not yet run; write paths surface the error so callers return a 5xx rather
than silently succeeding.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg2.errors  # type: ignore

from src.modules.task.repositories.interface import (
    ITaskRepository,
    Task,
    TASK_STATUS_VALUES,
)
from src.shared.domain.errors import ValidationError


# Fields accepted by `update(data=...)`. Anything else is silently dropped
# so a route accidentally forwarding untrusted keys into the repo cannot
# build arbitrary UPDATE columns.
_UPDATABLE_COLUMNS = {"subject", "description", "status", "due_at"}

# Columns that need the ::"TaskStatus" enum cast.
_ENUM_COLUMNS = {"status"}


class PostgresTaskRepository(ITaskRepository):
    def __init__(self, pool, logger=None) -> None:
        self._pool = pool
        self._logger = logger

    def _row_to_task(self, row: dict) -> Task:
        return Task(
            id=str(row["id"]),
            assigner_id=str(row["assigner_id"]) if row.get("assigner_id") else "",
            assignee_id=str(row["assignee_id"]) if row.get("assignee_id") else "",
            subject=row["subject"],
            description=row.get("description"),
            status=row.get("status", "OPEN"),
            due_at=row.get("due_at"),
            source_mail_id=str(row["source_mail_id"])
            if row.get("source_mail_id")
            else None,
            reply_token=row.get("reply_token"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _warn(self, event: str, **fields) -> None:
        if self._logger is not None:
            try:
                self._logger.warn(event, **fields)
            except Exception:
                pass

    # ── Reads ──────────────────────────────────────────────────────────────

    async def list_open_for_user(self, user_id: str) -> list[Task]:
        return await self.list_for_user(user_id, status="OPEN")

    async def find_by_id(self, task_id: str) -> Optional[Task]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT id, assigner_id, assignee_id, subject, description,
                               due_at, status::text AS status, source_mail_id,
                               reply_token, created_at, updated_at
                        FROM tasks
                        WHERE id = %s
                        """,
                        (task_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None
                    columns = [desc[0] for desc in cur.description]
                    return self._row_to_task(dict(zip(columns, row)))
                except psycopg2.errors.UndefinedTable:
                    self._warn("postgres_task_repo.table_missing", op="find_by_id")
                    conn.rollback()
                    return None
                except Exception as e:
                    self._warn("postgres_task_repo.find_failed", error=str(e))
                    conn.rollback()
                    return None
        finally:
            self._pool.putconn(conn)

    async def list_for_user(
        self, user_id: str, status: Optional[str] = None, limit: int = 50
    ) -> list[Task]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                try:
                    if status is not None:
                        cur.execute(
                            """
                            SELECT id, assigner_id, assignee_id, subject, description,
                                   due_at, status::text AS status, source_mail_id,
                                   reply_token, created_at, updated_at
                            FROM tasks
                            WHERE assignee_id = %s AND status = %s::"TaskStatus"
                            ORDER BY due_at ASC NULLS LAST, updated_at DESC
                            LIMIT %s
                            """,
                            (user_id, status, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT id, assigner_id, assignee_id, subject, description,
                                   due_at, status::text AS status, source_mail_id,
                                   reply_token, created_at, updated_at
                            FROM tasks
                            WHERE assignee_id = %s
                            ORDER BY due_at ASC NULLS LAST, updated_at DESC
                            LIMIT %s
                            """,
                            (user_id, limit),
                        )
                    rows = cur.fetchall()
                    if not rows:
                        return []
                    columns = [desc[0] for desc in cur.description]
                    return [self._row_to_task(dict(zip(columns, r))) for r in rows]
                except psycopg2.errors.UndefinedTable:
                    self._warn("postgres_task_repo.table_missing", op="list_for_user")
                    conn.rollback()
                    return []
                except Exception as e:
                    self._warn(
                        "postgres_task_repo.list_failed",
                        user_id=user_id,
                        error=str(e),
                    )
                    conn.rollback()
                    return []
        finally:
            self._pool.putconn(conn)

    # ── Writes ─────────────────────────────────────────────────────────────

    async def create(self, data: dict) -> Task:
        status = data.get("status", "OPEN")
        if status not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {status}")

        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        assignee_id = data["assignee_id"]
        assigner_id = data.get("assigner_id") or assignee_id

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tasks
                        (id, assigner_id, assignee_id, subject, description, due_at,
                         status, source_mail_id, reply_token, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::"TaskStatus", %s, %s, %s, %s)
                    """,
                    (
                        task_id,
                        assigner_id,
                        assignee_id,
                        data["subject"],
                        data.get("description"),
                        data.get("due_at"),
                        status,
                        data.get("source_mail_id"),
                        data.get("reply_token"),
                        now,
                        now,
                    ),
                )
                conn.commit()
            return Task(
                id=task_id,
                assigner_id=assigner_id,
                assignee_id=assignee_id,
                subject=data["subject"],
                description=data.get("description"),
                status=status,
                due_at=data.get("due_at"),
                source_mail_id=data.get("source_mail_id"),
                reply_token=data.get("reply_token"),
                created_at=now,
                updated_at=now,
            )
        finally:
            self._pool.putconn(conn)

    async def update_status(self, task_id: str, status: str) -> Optional[Task]:
        if status not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {status}")
        return await self.update(task_id, {"status": status})

    async def update(self, task_id: str, data: dict) -> Optional[Task]:
        safe = {k: v for k, v in data.items() if k in _UPDATABLE_COLUMNS}
        if "status" in safe and safe["status"] not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {safe['status']}")
        if not safe:
            return await self.find_by_id(task_id)

        set_clauses = []
        values: list = []
        for key, value in safe.items():
            if key in _ENUM_COLUMNS:
                set_clauses.append(f'{key} = %s::"TaskStatus"')
            else:
                set_clauses.append(f"{key} = %s")
            values.append(value)
        set_clauses.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(task_id)

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = %s",
                    values,
                )
                conn.commit()
            return await self.find_by_id(task_id)
        finally:
            self._pool.putconn(conn)

    async def delete(self, task_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                affected = cur.rowcount
                conn.commit()
            return affected > 0
        finally:
            self._pool.putconn(conn)
