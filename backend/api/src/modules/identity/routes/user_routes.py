"""User routes — /users/me, PATCH /users/me, signature CRUD."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse

from src.shared.domain.envelope import success_response, error_response
from src.shared.middleware.account_ownership import require_account_ownership

router = APIRouter()


# Fields a user may self-update via PATCH /users/me. Anything outside this set
# is silently ignored — role/email/status are admin-only.
_SELF_UPDATE_FIELDS = {"designation", "department", "responsibilities", "phone"}


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request):
    """Extract current user by verifying the Bearer JWT via auth_service."""
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


async def _audit(
    request: Request,
    *,
    actor: str,
    action: str,
    target: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> None:
    """Best-effort audit log write. Never raises — a broken audit store should
    not block a user action, but it will be visible in logs."""
    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is None:
        return
    try:
        await audit_repo.log_event(
            actor=actor,
            action=action,
            target=target,
            before=before,
            after=after,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass


def _user_to_dict(u) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "status": u.status,
        "mfaEnabled": u.mfa_enabled,
        "name": u.name,
        "designation": u.designation,
        "department": u.department,
        "responsibilities": u.responsibilities,
    }


def _sig_to_dict(sig) -> dict:
    return {
        "id": sig.id,
        "accountId": sig.account_id,
        "name": sig.name,
        "htmlTemplate": sig.html_template,
        "isDefault": sig.is_default,
        "createdAt": sig.created_at.isoformat() if sig.created_at else None,
    }


# ── Profile ──────────────────────────────────────────────────────────────────

@router.get("/users/me")
async def get_me(request: Request):
    trace_id = _trace_id(request)
    user_repo = request.app.state.user_repo

    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    db_user = await user_repo.find_by_id(user["id"])
    if not db_user:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", "User not found", trace_id),
        )

    return success_response(_user_to_dict(db_user), trace_id)


@router.patch("/users/me")
async def update_me(request: Request):
    """Update the logged-in user's profile. Role/email/status are admin-only.
    Writes an audit event with the before/after diff."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    data = {k: v for k, v in body.items() if k in _SELF_UPDATE_FIELDS and v is not None}
    if not data:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "No valid fields to update", trace_id),
        )

    user_repo = request.app.state.user_repo

    # Capture the before-snapshot for the audit diff (only the fields being changed).
    before_user = await user_repo.find_by_id(user["id"])
    if not before_user:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", "User not found", trace_id),
        )
    before_diff = {k: getattr(before_user, k, None) for k in data.keys()}

    updated = await user_repo.update(user["id"], data)
    if not updated:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", "User not found", trace_id),
        )

    await _audit(
        request,
        actor=user["id"],
        action="USER_PROFILE_UPDATE",
        target=user["id"],
        before=before_diff,
        after=data,
    )

    return success_response(_user_to_dict(updated), trace_id)


# ── Email Signatures ─────────────────────────────────────────────────────────
# Signatures are per linked_account (so each Google Workspace identity can
# have a separate signature). Ownership is enforced via
# `require_account_ownership` (for create) and `get_owner_user_id` (for update/
# delete). The repo takes care of the "one default per account" invariant.


def _signature_repo(request: Request):
    return getattr(request.app.state, "signature_repo", None)


@router.get("/users/me/signatures")
async def list_signatures(request: Request, accountId: Optional[str] = Query(None)):
    """List all signatures for the current user. Optionally filter by accountId."""
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(status_code=401, content=error_response("UNAUTHORIZED", "Not authenticated", trace_id))

    sig_repo = _signature_repo(request)
    if sig_repo is None:
        return JSONResponse(status_code=503, content=error_response("SERVICE_UNAVAILABLE", "Signature service not available", trace_id))

    if accountId:
        forbidden = await require_account_ownership(request, accountId, user["id"], trace_id)
        if forbidden:
            return forbidden
        sigs = await sig_repo.list_for_account(accountId)
    else:
        sigs = await sig_repo.list_for_user(user["id"])

    return success_response([_sig_to_dict(s) for s in sigs], trace_id)


@router.post("/users/me/signatures")
async def create_signature(request: Request):
    """Create a new email signature for a linked account."""
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(status_code=401, content=error_response("UNAUTHORIZED", "Not authenticated", trace_id))

    try:
        body = await request.json()
    except Exception:
        body = {}
    account_id = (body or {}).get("accountId")
    name = ((body or {}).get("name") or "").strip()
    html_template = ((body or {}).get("htmlTemplate") or "").strip()
    is_default = bool((body or {}).get("isDefault", False))

    if not account_id or not name or not html_template:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "accountId, name, and htmlTemplate are required", trace_id),
        )

    forbidden = await require_account_ownership(request, account_id, user["id"], trace_id)
    if forbidden:
        return forbidden

    sig_repo = _signature_repo(request)
    if sig_repo is None:
        return JSONResponse(status_code=503, content=error_response("SERVICE_UNAVAILABLE", "Signature service not available", trace_id))

    sig_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    sig = await sig_repo.create(
        id=sig_id,
        account_id=account_id,
        name=name,
        html_template=html_template,
        is_default=is_default,
        created_at=now,
    )

    await _audit(
        request,
        actor=user["id"],
        action="SIGNATURE_CREATE",
        target=sig.id,
        after={"accountId": sig.account_id, "name": sig.name, "isDefault": sig.is_default},
    )

    return success_response(_sig_to_dict(sig), trace_id)


@router.put("/users/me/signatures/{sig_id}")
async def update_signature(sig_id: str, request: Request):
    """Update an existing signature."""
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(status_code=401, content=error_response("UNAUTHORIZED", "Not authenticated", trace_id))

    sig_repo = _signature_repo(request)
    if sig_repo is None:
        return JSONResponse(status_code=503, content=error_response("SERVICE_UNAVAILABLE", "Signature service not available", trace_id))

    existing = await sig_repo.find_by_id(sig_id)
    if existing is None:
        return JSONResponse(status_code=404, content=error_response("NOT_FOUND", "Signature not found", trace_id))

    owner = await sig_repo.get_owner_user_id(sig_id)
    if owner != user["id"]:
        return JSONResponse(status_code=403, content=error_response("FORBIDDEN", "Not your signature", trace_id))

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    name = body.get("name", existing.name)
    html_template = body.get("htmlTemplate", existing.html_template)
    is_default = body.get("isDefault", existing.is_default)

    updated = await sig_repo.update(
        sig_id,
        name=name,
        html_template=html_template,
        is_default=bool(is_default),
    )

    await _audit(
        request,
        actor=user["id"],
        action="SIGNATURE_UPDATE",
        target=sig_id,
        before={"name": existing.name, "isDefault": existing.is_default},
        after={"name": updated.name, "isDefault": updated.is_default},
    )

    return success_response(_sig_to_dict(updated), trace_id)


@router.delete("/users/me/signatures/{sig_id}")
async def delete_signature(sig_id: str, request: Request):
    """Delete a signature."""
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(status_code=401, content=error_response("UNAUTHORIZED", "Not authenticated", trace_id))

    sig_repo = _signature_repo(request)
    if sig_repo is None:
        return JSONResponse(status_code=503, content=error_response("SERVICE_UNAVAILABLE", "Signature service not available", trace_id))

    existing = await sig_repo.find_by_id(sig_id)
    if existing is None:
        return JSONResponse(status_code=404, content=error_response("NOT_FOUND", "Signature not found", trace_id))

    owner = await sig_repo.get_owner_user_id(sig_id)
    if owner != user["id"]:
        return JSONResponse(status_code=403, content=error_response("FORBIDDEN", "Not your signature", trace_id))

    await sig_repo.delete(sig_id)

    await _audit(
        request,
        actor=user["id"],
        action="SIGNATURE_DELETE",
        target=sig_id,
        before={"accountId": existing.account_id, "name": existing.name},
    )

    return success_response({"deleted": True}, trace_id)
