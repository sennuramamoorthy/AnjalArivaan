"""PostgreSQL user repository."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.modules.identity.domain.user import User
from src.modules.identity.repositories.user_repository import IUserRepository


class PostgresUserRepository(IUserRepository):
    # Columns the repo will accept in `update(data=...)`. Anything else is
    # silently dropped. This exists so a route accidentally forwarding
    # untrusted keys into the repo cannot build arbitrary UPDATE columns.
    _UPDATABLE_COLUMNS = {
        "email",
        "password_hash",
        "mfa_enabled",
        "mfa_secret",
        "phone",
        "role",
        "status",
        "name",
        "designation",
        "department",
        "responsibilities",
    }

    def __init__(self, pool):
        self._pool = pool

    def _row_to_user(self, row: dict) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            mfa_enabled=row.get("mfa_enabled", False),
            mfa_secret=row.get("mfa_secret"),
            phone=row.get("phone"),
            role=row.get("role", "STAFF"),
            status=row.get("status", "ACTIVE"),
            name=row.get("email"),  # Fallback — real name from employee record
            designation=row.get("designation"),
            department=row.get("department"),
            responsibilities=row.get("responsibilities"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    async def find_by_id(self, user_id: str) -> Optional[User]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM app_users WHERE id = %s", (user_id,)
                )
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cur.description]
                return self._row_to_user(dict(zip(columns, row)))
        finally:
            self._pool.putconn(conn)

    async def find_by_email(self, email: str) -> Optional[User]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM app_users WHERE email = %s", (email.lower(),)
                )
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cur.description]
                return self._row_to_user(dict(zip(columns, row)))
        finally:
            self._pool.putconn(conn)

    async def create(self, data: dict[str, Any]) -> User:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO app_users
                       (id, email, password_hash, mfa_enabled, mfa_secret, phone, role, status, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        data["email"].lower(),
                        data["password_hash"],
                        data.get("mfa_enabled", False),
                        data.get("mfa_secret"),
                        data.get("phone"),
                        data.get("role", "STAFF"),
                        data.get("status", "ACTIVE"),
                        now,
                        now,
                    ),
                )
                conn.commit()
            return User(
                id=user_id,
                email=data["email"].lower(),
                password_hash=data["password_hash"],
                mfa_enabled=data.get("mfa_enabled", False),
                mfa_secret=data.get("mfa_secret"),
                phone=data.get("phone"),
                role=data.get("role", "STAFF"),
                status=data.get("status", "ACTIVE"),
                name=data.get("name", data["email"]),
                created_at=now,
                updated_at=now,
            )
        finally:
            self._pool.putconn(conn)

    async def update(self, user_id: str, data: dict[str, Any]) -> Optional[User]:
        # Drop any keys outside the whitelist so column identifiers can never
        # come from untrusted input (defense in depth against SQL injection).
        safe_data = {k: v for k, v in data.items() if k in self._UPDATABLE_COLUMNS}
        if not safe_data:
            return await self.find_by_id(user_id)
        set_clauses = []
        values = []
        for key, value in safe_data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
        set_clauses.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(user_id)

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE app_users SET {', '.join(set_clauses)} WHERE id = %s",
                    values,
                )
                conn.commit()
            return await self.find_by_id(user_id)
        finally:
            self._pool.putconn(conn)
