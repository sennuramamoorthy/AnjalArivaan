"""Admin routes — audit logs, user management, system health.

All endpoints require SUPER_ADMIN or DEPT_ADMIN role.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import error_response, success_response

router = APIRouter()

_ADMIN_ROLES = {"SUPER_ADMIN", "DEPT_ADMIN"}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request) -> Optional[dict]:
    """Extract current user via auth_service.verify_access_token."""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return None

    try:
        payload = auth_service.verify_access_token(token)
        return {
            "id": payload["sub"],
            "email": payload["email"],
            "role": payload["role"],
        }
    except Exception:
        return None


def _require_admin(user: dict, trace_id: str):
    """Return a 403 JSONResponse if user is not an admin, else None."""
    if user.get("role") not in _ADMIN_ROLES:
        return JSONResponse(
            status_code=403,
            content=error_response("FORBIDDEN", "Admin access required", trace_id),
        )
    return None


# ── Audit log routes ─────────────────────────────────────────────────────────


@router.get("/admin/audit-logs")
async def list_audit_logs(
    request: Request,
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    """Paginated audit log listing with optional actor/action filters."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Audit service not available", trace_id
            ),
        )

    events, total = await audit_repo.list_events(
        actor=actor, action=action, page=page, page_size=pageSize,
    )

    has_more = (page * pageSize) < total
    return success_response(
        {
            "events": events,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": has_more,
        },
        trace_id,
    )


@router.get("/admin/audit-logs/{event_id}")
async def get_audit_log(event_id: str, request: Request):
    """Single audit event detail."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Audit service not available", trace_id
            ),
        )

    event = await audit_repo.get_event(event_id)
    if event is None:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Audit event {event_id} not found", trace_id),
        )

    return success_response(event, trace_id)


# ── User management routes ───────────────────────────────────────────────────


@router.get("/admin/users")
async def list_users(
    request: Request,
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    """List all users (admin view)."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    admin_user_repo = getattr(request.app.state, "admin_user_repo", None)
    if admin_user_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "User service not available", trace_id
            ),
        )

    users, total = await admin_user_repo.list_users(
        role=role, status=status, page=page, page_size=pageSize,
    )

    has_more = (page * pageSize) < total
    return success_response(
        {
            "users": users,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": has_more,
        },
        trace_id,
    )


@router.post("/admin/users/{user_id}/suspend")
async def suspend_user(user_id: str, request: Request):
    """Set a user's status to SUSPENDED."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    admin_user_repo = getattr(request.app.state, "admin_user_repo", None)
    if admin_user_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "User service not available", trace_id
            ),
        )

    updated = await admin_user_repo.update_status(user_id, "SUSPENDED")
    if not updated:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"User {user_id} not found", trace_id),
        )

    # Log the admin action in audit trail
    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo:
        await audit_repo.log_event(
            actor=user["id"],
            action="USER_SUSPEND",
            target=user_id,
            after={"status": "SUSPENDED"},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return success_response({"success": True, "status": "SUSPENDED"}, trace_id)


@router.post("/admin/users/{user_id}/activate")
async def activate_user(user_id: str, request: Request):
    """Set a user's status to ACTIVE."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    admin_user_repo = getattr(request.app.state, "admin_user_repo", None)
    if admin_user_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "User service not available", trace_id
            ),
        )

    updated = await admin_user_repo.update_status(user_id, "ACTIVE")
    if not updated:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"User {user_id} not found", trace_id),
        )

    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo:
        await audit_repo.log_event(
            actor=user["id"],
            action="USER_ACTIVATE",
            target=user_id,
            after={"status": "ACTIVE"},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return success_response({"success": True, "status": "ACTIVE"}, trace_id)


# ── System health ────────────────────────────────────────────────────────────


@router.get("/admin/system-health")
async def system_health(request: Request):
    """Aggregated health info for the admin dashboard."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    forbidden = _require_admin(user, trace_id)
    if forbidden:
        return forbidden

    db_status = "ok"
    redis_status = "ok"
    outbox_pending = 0
    last_sync_at = None

    # Check database
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None:
        db_status = "unavailable"

    # Check Redis
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        redis_status = "unavailable"

    return success_response(
        {
            "database": db_status,
            "redis": redis_status,
            "outboxPending": outbox_pending,
            "lastSyncAt": last_sync_at,
        },
        trace_id,
    )
