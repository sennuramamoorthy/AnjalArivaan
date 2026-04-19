"""Audit service (PRD §8.3, §8.4, §8.5) — append-only."""
from __future__ import annotations

from app.core.events import DomainEvent, Events, bus
from app.domain.models.audit import AuditEvent, ConsentRecord
from app.repositories.audit import AuditRepository, ConsentRepository


class AuditService:
    def __init__(self, repo: AuditRepository) -> None:
        self.repo = repo

    async def record(
        self,
        *,
        actor_user_id: int | None,
        action: str,
        target_type: str,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before or {},
            after=after or {},
            ip=ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        self.repo.add(event)
        self.repo.commit()
        await bus.publish(
            DomainEvent(name=Events.AUDIT_ENTRY, payload={"id": event.id, "action": action})
        )
        return event

    def search(
        self, *, action: str | None = None, actor_user_id: int | None = None, limit: int = 100
    ) -> list[AuditEvent]:
        filters: dict = {}
        if action:
            filters["action"] = action
        if actor_user_id is not None:
            filters["actor_user_id"] = actor_user_id
        return list(self.repo.list(limit=limit, **filters))


class ConsentService:
    """DPDP Act 2023 consent ledger (PRD §8.3)."""

    def __init__(self, repo: ConsentRepository) -> None:
        self.repo = repo

    def grant(
        self,
        user_id: int,
        purpose: str,
        scope: list[str],
        proof: str = "",
    ) -> ConsentRecord:
        c = ConsentRecord(user_id=user_id, purpose=purpose, scope=scope, proof=proof)
        self.repo.add(c)
        self.repo.commit()
        return c

    def revoke(self, consent_id: int) -> ConsentRecord:
        from datetime import datetime, timezone

        c = self.repo.get_or_404(consent_id)
        c.revoked_at = datetime.now(timezone.utc)
        self.repo.commit()
        return c

    def active_for_user(self, user_id: int) -> list[ConsentRecord]:
        return self.repo.active_for_user(user_id)
