"""InMemorySignatureRepository — used by unit tests."""

from datetime import datetime
from typing import Optional

from src.modules.identity.repositories.signature_repository import (
    ISignatureRepository,
    Signature,
)


class InMemorySignatureRepository(ISignatureRepository):
    def __init__(self) -> None:
        self._store: dict[str, Signature] = {}
        # account_id → app_user_id. Tests seed this to mirror `linked_accounts`.
        self._owners: dict[str, str] = {}

    def register_account(self, account_id: str, app_user_id: str) -> None:
        """Test helper — tells the repo which user owns each account so that
        `get_owner_user_id` can answer ownership questions."""
        self._owners[account_id] = app_user_id

    async def find_by_id(self, signature_id: str) -> Optional[Signature]:
        return self._store.get(signature_id)

    async def find_default_for_account(self, account_id: str) -> Optional[Signature]:
        for s in self._store.values():
            if s.account_id == account_id and s.is_default:
                return s
        return None

    async def list_for_account(self, account_id: str) -> list[Signature]:
        rows = [s for s in self._store.values() if s.account_id == account_id]
        rows.sort(key=lambda s: (not s.is_default, -s.created_at.timestamp()))
        return rows

    async def list_for_user(self, app_user_id: str) -> list[Signature]:
        user_accounts = {
            acc_id for acc_id, uid in self._owners.items() if uid == app_user_id
        }
        rows = [s for s in self._store.values() if s.account_id in user_accounts]
        rows.sort(key=lambda s: (not s.is_default, -s.created_at.timestamp()))
        return rows

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
        if is_default:
            for s in self._store.values():
                if s.account_id == account_id and s.is_default:
                    s.is_default = False
        sig = Signature(
            id=id,
            account_id=account_id,
            name=name,
            html_template=html_template,
            is_default=is_default,
            created_at=created_at,
        )
        self._store[id] = sig
        return sig

    async def update(
        self,
        signature_id: str,
        *,
        name: str,
        html_template: str,
        is_default: bool,
    ) -> Optional[Signature]:
        sig = self._store.get(signature_id)
        if sig is None:
            return None
        if is_default and not sig.is_default:
            for s in self._store.values():
                if s.account_id == sig.account_id and s.id != sig.id and s.is_default:
                    s.is_default = False
        sig.name = name
        sig.html_template = html_template
        sig.is_default = is_default
        return sig

    async def delete(self, signature_id: str) -> bool:
        return self._store.pop(signature_id, None) is not None

    async def get_owner_user_id(self, signature_id: str) -> Optional[str]:
        sig = self._store.get(signature_id)
        if sig is None:
            return None
        return self._owners.get(sig.account_id)
