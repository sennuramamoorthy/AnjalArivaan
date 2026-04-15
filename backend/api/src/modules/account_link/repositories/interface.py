from abc import ABC, abstractmethod

from src.modules.account_link.domain.linked_account import LinkedAccount


class ILinkedAccountRepository(ABC):
    @abstractmethod
    async def save(self, account: LinkedAccount) -> LinkedAccount:
        """Persist a linked account (insert or update)."""
        ...

    @abstractmethod
    async def find_by_id(self, id: str) -> LinkedAccount | None:
        """Return a linked account by its primary key, or None."""
        ...

    @abstractmethod
    async def find_by_user(self, app_user_id: str) -> list[LinkedAccount]:
        """Return all linked accounts belonging to a user."""
        ...

    @abstractmethod
    async def find_by_email_and_user(
        self, google_email: str, app_user_id: str
    ) -> LinkedAccount | None:
        """Return a linked account matching the Google email for a given user."""
        ...

    @abstractmethod
    async def update_status(self, id: str, status: str) -> None:
        """Update the status field of a linked account."""
        ...
