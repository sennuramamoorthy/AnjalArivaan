"""Audit log immutability (PRD §8.4)."""
import pytest

from app.domain.models.audit import AuditEvent
from app.repositories.audit import AuditRepository


def test_audit_repo_rejects_delete(db):
    repo = AuditRepository(db)
    evt = AuditEvent(actor_user_id=1, action="test", target_type="x", target_id="1")
    repo.add(evt)
    repo.commit()
    with pytest.raises(PermissionError):
        repo.delete(evt)
