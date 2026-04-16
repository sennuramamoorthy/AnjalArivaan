"""PostgreSQL task repository.

Reads from the ``tasks`` table. In Phase 1 the table may not yet exist
(task extraction isn't fully deployed) — any SELECT error is logged as
a warning and degrades to an empty list so the daily briefing still
renders.
"""

from __future__ import annotations

from src.modules.task.repositories.interface import ITaskRepository, Task


class PostgresTaskRepository(ITaskRepository):
    def __init__(self, pool, logger=None) -> None:
        self._pool = pool
        self._logger = logger

    def _row_to_task(self, row: dict) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            status=row.get("status", "PENDING"),
            due_at=row.get("due_at"),
            assigned_to=row.get("assigned_to"),
            source_mail_id=row.get("source_mail_id"),
        )

    async def list_pending_for_user(self, user_id: str) -> list[Task]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT id, title, status, due_at, assigned_to,
                               source_mail_id, created_at, updated_at
                        FROM tasks
                        WHERE assigned_to = %s AND status = %s
                        ORDER BY due_at ASC NULLS LAST
                        """,
                        (user_id, "PENDING"),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        return []
                    columns = [desc[0] for desc in cur.description]
                    return [self._row_to_task(dict(zip(columns, r))) for r in rows]
                except Exception as e:
                    if self._logger is not None:
                        self._logger.warn(
                            "postgres_task_repo.list_failed",
                            user_id=user_id,
                            error=e,
                        )
                    # Most common cause in Phase 1: tasks table not yet
                    # migrated. Degrade to empty list.
                    conn.rollback()
                    return []
        finally:
            self._pool.putconn(conn)
