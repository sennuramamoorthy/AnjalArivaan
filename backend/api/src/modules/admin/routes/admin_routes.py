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

# Assignable roles for new users. Keep in sync with UserRole in
# src/modules/identity/domain/user.py.
_ASSIGNABLE_ROLES = {"SUPER_ADMIN", "DEPT_ADMIN", "VC", "REGISTRAR", "DEAN", "HOD", "STAFF"}


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


# ── Urgency escalation visibility ────────────────────────────────────────────


@router.get("/admin/urgency-events")
async def list_urgency_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
):
    """Recent urgency_outbox rows — dispatched and pending. SUPER_ADMIN only."""
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

    repo = getattr(request.app.state, "urgency_outbox_repo", None)
    if repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Urgency outbox not available", trace_id
            ),
        )

    rows = await repo.list_recent(limit=limit)
    return success_response(
        {
            "events": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "account_id": r.account_id,
                    "thread_id": r.thread_id,
                    "message_id": r.message_id,
                    "matched_rules": r.matched_rules,
                    "reason": r.reason,
                    "detected_deadline": r.detected_deadline,
                    "line_manager_email": r.line_manager_email,
                    "whatsapp_template": r.whatsapp_template,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                }
                for r in rows
            ],
            "count": len(rows),
        },
        trace_id,
    )


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


@router.post("/admin/users")
async def create_user(request: Request):
    """Onboard a new user. Admin supplies email, name, role and an initial
    password; the user is created ACTIVE and can log in immediately. Writes
    an audit event. Password is never echoed back in the response.
    """
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

    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Identity service not available", trace_id
            ),
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "Invalid JSON body", trace_id),
        )
    if not isinstance(body, dict):
        body = {}

    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip()
    role = (body.get("role") or "STAFF").strip()

    # Shape validation — AuthService.register also validates email/password,
    # but we catch role + empty fields here so the error stays structured.
    if not email or "@" not in email:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", "Valid email is required", trace_id),
        )
    if len(password) < 8:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", "Password must be at least 8 characters", trace_id),
        )
    if not name:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", "Name is required", trace_id),
        )
    if role not in _ASSIGNABLE_ROLES:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", f"Role must be one of {sorted(_ASSIGNABLE_ROLES)}", trace_id),
        )

    # Map typed service errors to HTTP status codes. Anything else is an
    # internal error — do NOT surface the raw exception text to the caller.
    from src.shared.domain.errors import (
        AppError,
        UserAlreadyExistsError,
        ValidationError,
    )

    try:
        new_user = await auth_service.register({
            "email": email,
            "password": password,
            "name": name,
            "role": role,
        })
    except UserAlreadyExistsError:
        return JSONResponse(
            status_code=409,
            content=error_response("USER_ALREADY_EXISTS", "A user with this email already exists", trace_id),
        )
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", str(e), trace_id),
        )
    except AppError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=error_response(e.code, e.message, trace_id),
        )
    except Exception:
        logger = getattr(request.app.state, "logger", None)
        if logger is not None:
            logger.error("admin.create_user failed", trace_id=trace_id)
        return JSONResponse(
            status_code=500,
            content=error_response("INTERNAL_ERROR", "Failed to create user", trace_id),
        )

    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo:
        await audit_repo.log_event(
            actor=user["id"],
            action="USER_CREATE",
            target=new_user.id,
            after={"email": new_user.email, "role": role},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return success_response(
        {
            "id": new_user.id,
            "email": new_user.email,
            "name": getattr(new_user, "name", None) or new_user.email.split("@", 1)[0],
            "role": role,
            "status": "ACTIVE",
            "mfaEnabled": False,
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
