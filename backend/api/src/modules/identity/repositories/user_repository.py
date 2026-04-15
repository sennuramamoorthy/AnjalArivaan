"""User repository interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.modules.identity.domain.user import User


class IUserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> User: ...

    @abstractmethod
    async def update(self, user_id: str, data: dict[str, Any]) -> Optional[User]: ...
