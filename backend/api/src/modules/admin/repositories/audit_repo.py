"""Audit event repository — abstract interface.

Append-only audit log required by DPDP Act 2023 compliance.
All admin actions and AI-generated content land here.
"""

from abc import ABC, abstractmethod
from typing import Optional


class IAuditRepository(ABC):
    @abstractmethod
    async def log_event(
        self,
        actor: str,
        action: str,
        target: str,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        content_hash: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Persist an audit event. Returns the generated event id (uuid)."""

    @abstractmethod
    async def list_events(
        self,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """Return (events, total_count) with optional filters and pagination."""

    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[dict]:
        """Return a single audit event by id, or None."""
