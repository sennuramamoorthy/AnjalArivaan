"""InMemoryAdminUserRepository — used in unit tests."""

from typing import Optional

from .admin_user_repo import IAdminUserRepository


class InMemoryAdminUserRepository(IAdminUserRepository):
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def seed(self, user: dict) -> None:
        """Add a user dict to the store (test helper)."""
        self._store[user["id"]] = dict(user)

    async def list_users(
        self,
        *,
        role: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        users = list(self._store.values())
        if role:
            users = [u for u in users if u.get("role") == role]
        if status:
            users = [u for u in users if u.get("status") == status]

        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size
        return users[start:end], total

    async def get_user(self, user_id: str) -> Optional[dict]:
        return self._store.get(user_id)

    async def update_status(self, user_id: str, status: str) -> bool:
        user = self._store.get(user_id)
        if user is None:
            return False
        user["status"] = status
        return True
