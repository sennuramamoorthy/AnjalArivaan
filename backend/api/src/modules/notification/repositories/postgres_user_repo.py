"""
PostgresNotificationUserRepository — queries app_users + employees + linked_accounts
to build the user dict the notification service needs.

Returns: {id, role, phone, reporting_to_email, linked_account_id, gmail_token}
"""

import asyncio
import logging

import psycopg2
import psycopg2.extras

from src.modules.notification.repositories.interface import IUserRepository

logger = logging.getLogger(__name__)

_USER_QUERY = """
    SELECT
        au.id,
        au.role,
        au.phone,
        mgr_au.email AS reporting_to_email,
        la.id AS linked_account_id,
        la.vault_ref AS gmail_token
    FROM app_users au
    LEFT JOIN employees emp ON emp.app_user_id = au.id
    LEFT JOIN employees mgr ON mgr.id = emp.reporting_to_id
    LEFT JOIN app_users mgr_au ON mgr_au.id = mgr.app_user_id
    LEFT JOIN LATERAL (
        SELECT id, vault_ref
        FROM linked_accounts
        WHERE app_user_id = au.id AND status = 'ACTIVE'
        ORDER BY created_at ASC
        LIMIT 1
    ) la ON TRUE
    WHERE au.id = %s
"""


class PostgresNotificationUserRepository(IUserRepository):
    """Production user repository for the notification module.

    Joins app_users → employees → reporting manager → linked_accounts
    to resolve all fields the UrgencyNotificationService requires.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    async def get_user(self, user_id: str) -> dict | None:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._get_user_sync(user_id))

    def _get_user_sync(self, user_id: str) -> dict | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(_USER_QUERY, (user_id,))
                    row = cur.fetchone()
                    if row is None:
                        return None
                    return dict(row)
        except Exception:
            logger.exception("Failed to fetch user for notification", extra={"user_id": user_id})
            return None
