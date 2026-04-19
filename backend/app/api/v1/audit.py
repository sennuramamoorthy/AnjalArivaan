"""Audit + consent endpoints."""
from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUser,
    get_audit_service,
    get_consent_service,
    require_super_admin,
)
from app.services.audit_service import AuditService, ConsentService

router = APIRouter()


@router.get("/events", dependencies=[Depends(require_super_admin)])
def list_events(
    action: str | None = None,
    actor_user_id: int | None = None,
    limit: int = 100,
    svc: AuditService = Depends(get_audit_service),
):
    events = svc.search(action=action, actor_user_id=actor_user_id, limit=limit)
    return [
        {
            "id": e.id,
            "actor_user_id": e.actor_user_id,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]


@router.post("/consents")
def grant_consent(
    purpose: str,
    scope: list[str],
    user: CurrentUser,
    svc: ConsentService = Depends(get_consent_service),
):
    c = svc.grant(user.id, purpose, scope, proof=f"user:{user.id}")
    return {"id": c.id, "purpose": c.purpose, "scope": c.scope}


@router.get("/consents")
def my_consents(user: CurrentUser, svc: ConsentService = Depends(get_consent_service)):
    return [
        {"id": c.id, "purpose": c.purpose, "scope": c.scope, "granted_at": c.granted_at.isoformat()}
        for c in svc.active_for_user(user.id)
    ]


@router.post("/consents/{consent_id}/revoke")
def revoke_consent(consent_id: int, svc: ConsentService = Depends(get_consent_service)):
    c = svc.revoke(consent_id)
    return {"id": c.id, "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None}
