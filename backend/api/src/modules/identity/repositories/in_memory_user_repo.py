"""In-memory user repository for unit tests."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.modules.identity.domain.user import User
from src.modules.identity.repositories.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self):
        self._users: dict[str, User] = {}

    async def find_by_id(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    async def find_by_email(self, email: str) -> Optional[User]:
        for user in self._users.values():
            if user.email == email.lower():
                return user
        return None

    async def create(self, data: dict[str, Any]) -> User:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        user = User(
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
        self._users[user_id] = user
        return user

    async def update(self, user_id: str, data: dict[str, Any]) -> Optional[User]:
        user = self._users.get(user_id)
        if user is None:
            return None
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        return user
