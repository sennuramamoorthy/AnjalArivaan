"""PostgresAdminUserRepository — reads/updates the app_users table for admin operations."""

import asyncio
from typing import Optional

from .admin_user_repo import IAdminUserRepository


class PostgresAdminUserRepository(IAdminUserRepository):
    def __init__(self, conn_pool) -> None:
        self._pool = conn_pool

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    async def list_users(
        self,
        *,
        role: Optional[str] = None,
        status: Optional[str] = None,
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
                    if role:
                        clauses.append("role = %s")
                        params.append(role)
                    if status:
                        clauses.append("status = %s")
                        params.append(status)

                    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

                    cur.execute(f"SELECT count(*) FROM app_users {where}", params)
                    total = cur.fetchone()[0]

                    offset = (page - 1) * page_size
                    cur.execute(
                        f"""
                        SELECT id, email, name, role, status, mfa_enabled, created_at
                        FROM app_users {where}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        params + [page_size, offset],
                    )
                    rows = cur.fetchall()
                    cols = ["id", "email", "name", "role", "status", "mfaEnabled", "createdAt"]
                    users = [dict(zip(cols, r)) for r in rows]
                    for u in users:
                        if u.get("createdAt"):
                            u["createdAt"] = u["createdAt"].isoformat()
                    return users, total
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _query)

    async def get_user(self, user_id: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()

        def _query():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, email, name, role, status, mfa_enabled, created_at
                        FROM app_users WHERE id = %s
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None
                    cols = ["id", "email", "name", "role", "status", "mfaEnabled", "createdAt"]
                    user = dict(zip(cols, row))
                    if user.get("createdAt"):
                        user["createdAt"] = user["createdAt"].isoformat()
                    return user
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _query)

    async def update_status(self, user_id: str, status: str) -> bool:
        loop = asyncio.get_event_loop()

        def _update():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE app_users SET status = %s WHERE id = %s",
                        (status, user_id),
                    )
                conn.commit()
                return cur.rowcount > 0
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _update)
