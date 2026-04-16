"""PostgreSQL implementation of ISignatureRepository."""

from datetime import datetime
from typing import Optional

from src.modules.identity.repositories.signature_repository import (
    ISignatureRepository,
    Signature,
)


class PostgresSignatureRepository(ISignatureRepository):
    """Thin wrapper over `signatures` and `linked_accounts` tables.

    Ownership (which app user can touch a signature) is derived via the
    `linked_accounts.app_user_id` FK — callers do not pass a user id.
    """

    def __init__(self, pool) -> None:
        self._pool = pool

    @staticmethod
    def _row_to_signature(row: dict) -> Signature:
        return Signature(
            id=row["id"],
            account_id=row["account_id"],
            name=row["name"],
            html_template=row["html_template"],
            is_default=row["is_default"],
            created_at=row["created_at"],
        )

    def _cols(self, cur) -> list[str]:
        return [d[0] for d in cur.description]

    async def find_by_id(self, signature_id: str) -> Optional[Signature]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM signatures WHERE id = %s", (signature_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                cols = self._cols(cur)
                return self._row_to_signature(dict(zip(cols, row)))
        finally:
            self._pool.putconn(conn)

    async def find_default_for_account(self, account_id: str) -> Optional[Signature]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM signatures WHERE account_id = %s AND is_default = true LIMIT 1",
                    (account_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cols = self._cols(cur)
                return self._row_to_signature(dict(zip(cols, row)))
        finally:
            self._pool.putconn(conn)

    async def list_for_account(self, account_id: str) -> list[Signature]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM signatures WHERE account_id = %s "
                    "ORDER BY is_default DESC, created_at DESC",
                    (account_id,),
                )
                cols = self._cols(cur)
                return [self._row_to_signature(dict(zip(cols, r))) for r in cur.fetchall()]
        finally:
            self._pool.putconn(conn)

    async def list_for_user(self, app_user_id: str) -> list[Signature]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT s.* FROM signatures s
                       JOIN linked_accounts la ON la.id = s.account_id
                       WHERE la.app_user_id = %s
                       ORDER BY s.is_default DESC, s.created_at DESC""",
                    (app_user_id,),
                )
                cols = self._cols(cur)
                return [self._row_to_signature(dict(zip(cols, r))) for r in cur.fetchall()]
        finally:
            self._pool.putconn(conn)

    async def create(
        self,
        *,
        id: str,
        account_id: str,
        name: str,
        html_template: str,
        is_default: bool,
        created_at: datetime,
    ) -> Signature:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                if is_default:
                    cur.execute(
                        "UPDATE signatures SET is_default = false WHERE account_id = %s",
                        (account_id,),
                    )
                cur.execute(
                    """INSERT INTO signatures (id, account_id, name, html_template, is_default, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (id, account_id, name, html_template, is_default, created_at),
                )
                conn.commit()
        finally:
            self._pool.putconn(conn)
        return Signature(
            id=id,
            account_id=account_id,
            name=name,
            html_template=html_template,
            is_default=is_default,
            created_at=created_at,
        )

    async def update(
        self,
        signature_id: str,
        *,
        name: str,
        html_template: str,
        is_default: bool,
    ) -> Optional[Signature]:
        existing = await self.find_by_id(signature_id)
        if existing is None:
            return None
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                if is_default and not existing.is_default:
                    cur.execute(
                        "UPDATE signatures SET is_default = false "
                        "WHERE account_id = %s AND id != %s",
                        (existing.account_id, signature_id),
                    )
                cur.execute(
                    "UPDATE signatures SET name = %s, html_template = %s, is_default = %s "
                    "WHERE id = %s",
                    (name, html_template, is_default, signature_id),
                )
                conn.commit()
        finally:
            self._pool.putconn(conn)
        return Signature(
            id=signature_id,
            account_id=existing.account_id,
            name=name,
            html_template=html_template,
            is_default=is_default,
            created_at=existing.created_at,
        )

    async def delete(self, signature_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM signatures WHERE id = %s", (signature_id,))
                deleted = cur.rowcount > 0
                conn.commit()
            return deleted
        finally:
            self._pool.putconn(conn)

    async def get_owner_user_id(self, signature_id: str) -> Optional[str]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT la.app_user_id FROM signatures s
                       JOIN linked_accounts la ON la.id = s.account_id
                       WHERE s.id = %s""",
                    (signature_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            self._pool.putconn(conn)
