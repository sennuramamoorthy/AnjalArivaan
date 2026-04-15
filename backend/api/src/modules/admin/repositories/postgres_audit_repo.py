"""PostgresAuditRepository — writes to the audit_events table.

Table schema:
    id              uuid PRIMARY KEY,
    actor           text NOT NULL,
    action          text NOT NULL,
    target          text NOT NULL,
    before          jsonb,
    after           jsonb,
    generated_content_hash text,
    ip_address      text,
    user_agent      text,
    ts              timestamptz NOT NULL DEFAULT now()
"""

import asyncio
import json
import uuid
from typing import Optional

from .audit_repo import IAuditRepository


class PostgresAuditRepository(IAuditRepository):
    def __init__(self, conn_pool) -> None:
        self._pool = conn_pool

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # interface
    # ------------------------------------------------------------------

    async def log_event(
        self,
        actor: str,
        action: str,
        target: str,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        content_hash: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()

        def _insert():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audit_events
                            (id, actor, action, target, before, after,
                             generated_content_hash, ip_address, user_agent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event_id,
                            actor,
                            action,
                            target,
                            json.dumps(before) if before else None,
                            json.dumps(after) if after else None,
                            content_hash,
                            ip,
                            user_agent,
                        ),
                    )
                conn.commit()
            finally:
                self._put_conn(conn)
            return event_id

        return await loop.run_in_executor(None, _insert)

    async def list_events(
        self,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        loop = asyncio.get_event_loop()

        def _query():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    clauses: list[str] = []
                    params: list = []
                    if actor:
                        clauses.append("actor = %s")
                        params.append(actor)
                    if action:
                        clauses.append("action = %s")
                        params.append(action)

                    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

                    cur.execute(
                        f"SELECT count(*) FROM audit_events {where}",
                        params,
                    )
                    total = cur.fetchone()[0]

                    offset = (page - 1) * page_size
                    cur.execute(
                        f"""
                        SELECT id, actor, action, target, before, after,
                               generated_content_hash, ip_address, user_agent, ts
                        FROM audit_events {where}
                        ORDER BY ts DESC
                        LIMIT %s OFFSET %s
                        """,
                        params + [page_size, offset],
                    )
                    rows = cur.fetchall()
                    cols = [
                        "id", "actor", "action", "target", "before", "after",
                        "generatedContentHash", "ipAddress", "userAgent", "ts",
                    ]
                    events = [dict(zip(cols, r)) for r in rows]
                    for e in events:
                        if e.get("ts"):
                            e["ts"] = e["ts"].isoformat()
                    return events, total
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _query)

    async def get_event(self, event_id: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()

        def _query():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, actor, action, target, before, after,
                               generated_content_hash, ip_address, user_agent, ts
                        FROM audit_events
                        WHERE id = %s
                        """,
                        (event_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None
                    cols = [
                        "id", "actor", "action", "target", "before", "after",
                        "generatedContentHash", "ipAddress", "userAgent", "ts",
                    ]
                    event = dict(zip(cols, row))
                    if event.get("ts"):
                        event["ts"] = event["ts"].isoformat()
                    return event
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _query)
