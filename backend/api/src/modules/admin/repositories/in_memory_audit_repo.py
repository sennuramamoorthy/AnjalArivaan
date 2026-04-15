"""InMemoryAuditRepository — used in unit tests."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from .audit_repo import IAuditRepository


class InMemoryAuditRepository(IAuditRepository):
    def __init__(self) -> None:
        self._store: list[dict] = []

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
        event_id = str(uuid.uuid4())
        self._store.append(
            {
                "id": event_id,
                "actor": actor,
                "action": action,
                "target": target,
                "before": before,
                "after": after,
                "generatedContentHash": content_hash,
                "ipAddress": ip,
                "userAgent": user_agent,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        return event_id

    async def list_events(
        self,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        filtered = list(self._store)
        if actor:
            filtered = [e for e in filtered if e["actor"] == actor]
        if action:
            filtered = [e for e in filtered if e["action"] == action]

        # newest first
        filtered.sort(key=lambda e: e["ts"], reverse=True)
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    async def get_event(self, event_id: str) -> Optional[dict]:
        for e in self._store:
            if e["id"] == event_id:
                return e
        return None
