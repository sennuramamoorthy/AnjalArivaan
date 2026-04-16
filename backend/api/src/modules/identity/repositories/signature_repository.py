"""Email signature repository interface.

Signatures belong to a `linked_account` (so each Google Workspace identity can
have its own). Repos hide the underlying storage (Postgres) and the
`is_default` invariant (at most one default per account).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Signature:
    id: str
    account_id: str
    name: str
    html_template: str
    is_default: bool
    created_at: datetime


class ISignatureRepository(ABC):
    @abstractmethod
    async def find_by_id(self, signature_id: str) -> Optional[Signature]:
        """Return a signature by its primary key, or None."""

    @abstractmethod
    async def find_default_for_account(self, account_id: str) -> Optional[Signature]:
        """Return the default signature for an account, or None."""

    @abstractmethod
    async def list_for_account(self, account_id: str) -> list[Signature]:
        """Return all signatures for an account, default first then newest first."""

    @abstractmethod
    async def list_for_user(self, app_user_id: str) -> list[Signature]:
        """Return all signatures across the user's linked accounts."""

    @abstractmethod
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
        """Insert a new signature. If `is_default` is True the repo must
        atomically clear any other default for the same account."""

    @abstractmethod
    async def update(
        self,
        signature_id: str,
        *,
        name: str,
        html_template: str,
        is_default: bool,
    ) -> Optional[Signature]:
        """Update name/html/default. If is_default flips to True the repo
        must atomically clear the previous default for the same account."""

    @abstractmethod
    async def delete(self, signature_id: str) -> bool:
        """Delete a signature. Returns True if a row was removed."""

    @abstractmethod
    async def get_owner_user_id(self, signature_id: str) -> Optional[str]:
        """Return the `app_user_id` that owns the signature's linked_account,
        or None if the signature doesn't exist. Used for ownership checks."""
