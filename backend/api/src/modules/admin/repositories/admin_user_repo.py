"""Admin user repository — abstract interface.

Provides read and status-update operations on the app_users table
for the super-admin console.
"""

from abc import ABC, abstractmethod
from typing import Optional


class IAdminUserRepository(ABC):
    @abstractmethod
    async def list_users(
        self,
        *,
        role: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """Return (users, total_count) with optional role/status filter."""

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[dict]:
        """Return a single user dict by id, or None."""

    @abstractmethod
    async def update_status(self, user_id: str, status: str) -> bool:
        """Set the user's status. Returns True if the row was found and updated."""
