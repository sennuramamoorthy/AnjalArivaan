"""InMemoryLinkedAccountRepository — test double for unit tests."""

from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.interface import ILinkedAccountRepository


class InMemoryLinkedAccountRepository(ILinkedAccountRepository):
    def __init__(self) -> None:
        self._store: dict[str, LinkedAccount] = {}

    async def save(self, account: LinkedAccount) -> LinkedAccount:
        self._store[account.id] = account
        return account

    async def find_by_id(self, id: str) -> LinkedAccount | None:
        return self._store.get(id)

    async def find_by_user(self, app_user_id: str) -> list[LinkedAccount]:
        return [a for a in self._store.values() if a.app_user_id == app_user_id]

    async def find_by_email_and_user(
        self, google_email: str, app_user_id: str
    ) -> LinkedAccount | None:
        for account in self._store.values():
            if (
                account.google_email == google_email
                and account.app_user_id == app_user_id
            ):
                return account
        return None

    async def update_status(self, id: str, status: str) -> None:
        account = self._store.get(id)
        if account is not None:
            account.status = status
