"""
PostgresLinkedAccountRepository — production implementation backed by Postgres.

Expects a `linked_accounts` table:
  id TEXT PRIMARY KEY,
  app_user_id TEXT NOT NULL,
  google_email TEXT NOT NULL,
  workspace_domain TEXT NOT NULL,
  scopes TEXT[] NOT NULL,
  vault_ref TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  last_sync_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
"""

import logging

import psycopg2
import psycopg2.extras

from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.interface import ILinkedAccountRepository

logger = logging.getLogger(__name__)


class PostgresLinkedAccountRepository(ILinkedAccountRepository):
    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    def _row_to_entity(self, row: dict) -> LinkedAccount:
        return LinkedAccount(
            id=row["id"],
            app_user_id=row["app_user_id"],
            google_email=row["google_email"],
            workspace_domain=row["workspace_domain"],
            scopes=list(row["scopes"]) if row["scopes"] else [],
            vault_ref=row["vault_ref"],
            status=row["status"],
            last_sync_at=row["last_sync_at"],
            created_at=row["created_at"],
        )

    async def save(self, account: LinkedAccount) -> LinkedAccount:
        sql = """
            INSERT INTO linked_accounts
                (id, app_user_id, google_email, workspace_domain, scopes,
                 vault_ref, status, last_sync_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                google_email = EXCLUDED.google_email,
                workspace_domain = EXCLUDED.workspace_domain,
                scopes = EXCLUDED.scopes,
                vault_ref = EXCLUDED.vault_ref,
                status = EXCLUDED.status,
                last_sync_at = EXCLUDED.last_sync_at,
                updated_at = NOW()
            RETURNING *
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    account.id,
                    account.app_user_id,
                    account.google_email,
                    account.workspace_domain,
                    account.scopes,
                    account.vault_ref,
                    account.status,
                    account.last_sync_at,
                    account.created_at,
                ))
                row = cur.fetchone()
                conn.commit()
        return self._row_to_entity(row)

    async def find_by_id(self, id: str) -> LinkedAccount | None:
        sql = "SELECT * FROM linked_accounts WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (id,))
                row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    async def find_by_user(self, app_user_id: str) -> list[LinkedAccount]:
        sql = "SELECT * FROM linked_accounts WHERE app_user_id = %s ORDER BY created_at"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (app_user_id,))
                rows = cur.fetchall()
        return [self._row_to_entity(row) for row in rows]

    async def find_by_email_and_user(
        self, google_email: str, app_user_id: str
    ) -> LinkedAccount | None:
        sql = """
            SELECT * FROM linked_accounts
            WHERE google_email = %s AND app_user_id = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (google_email, app_user_id))
                row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    async def update_status(self, id: str, status: str) -> None:
        sql = "UPDATE linked_accounts SET status = %s, updated_at = NOW() WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, id))
                conn.commit()
