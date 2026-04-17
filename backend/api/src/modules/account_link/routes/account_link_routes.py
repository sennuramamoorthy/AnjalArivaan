"""Account Link routes — Google Workspace OAuth linking flow.

GET  /accounts/linked                   — list linked accounts for authenticated user
POST /accounts/link/initiate            — start OAuth flow
GET  /accounts/link/callback            — Google redirects here with code + state
POST /accounts/linked/{id}/sync         — trigger a background Gmail sync
DELETE /accounts/linked/{id}            — revoke a linked account (soft — status → REVOKED)
DELETE /accounts/linked/{id}/permanent  — hard-delete a revoked account (removes the row)
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import success_response, error_response
from src.shared.middleware.account_ownership import require_account_ownership

router = APIRouter()


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request) -> dict | None:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return None
    try:
        payload = auth_service.verify_access_token(token)
        return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
    except Exception:
        return None


@router.get("/accounts/linked")
async def get_linked_accounts(request: Request):
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    service = getattr(request.app.state, "account_link_service", None)
    if service is None:
        return success_response([], trace_id)

    accounts = await service.get_linked_accounts(user["id"])
    return success_response(
        [_serialize_account(a) for a in accounts],
        trace_id,
    )


@router.post("/accounts/link/initiate")
async def initiate_link(request: Request):
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    service = getattr(request.app.state, "account_link_service", None)
    if service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Account link service not configured", trace_id
            ),
        )

    body = await request.json()
    redirect_uri = body.get("redirectUri", "")
    scopes = body.get("scopes", [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar.events",
    ])

    result = await service.initiate_oauth(
        user_id=user["id"],
        redirect_uri=redirect_uri,
        scopes=scopes,
    )
    return success_response(
        {"authorizationUrl": result["authorization_url"], "state": result["state"]},
        trace_id,
    )


@router.get("/accounts/link/callback")
async def oauth_callback(request: Request, code: str = "", state: str = ""):
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    service = getattr(request.app.state, "account_link_service", None)
    if service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Account link service not configured", trace_id
            ),
        )

    if not code or not state:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST", "Missing code or state parameter", trace_id
            ),
        )

    try:
        account = await service.complete_oauth(
            user_id=user["id"], code=code, state=state
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_STATE", str(e), trace_id),
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content=error_response(
                "OAUTH_EXCHANGE_FAILED",
                f"Failed to complete Google OAuth: {e}",
                trace_id,
            ),
        )

    # D16: provision the per-account Qdrant namespace BEFORE sync kicks off, so
    # the first sync has somewhere to write embeddings. Never raises — a
    # Qdrant outage must not block the user's account link.
    vector_store = getattr(request.app.state, "vector_store", None)
    logger = getattr(request.app.state, "logger", None)
    if vector_store is not None:
        from src.modules.ai.services.account_lifecycle import (
            ensure_account_vector_namespace,
        )
        await ensure_account_vector_namespace(
            account_id=account.id,
            vector_store=vector_store,
            logger=logger,
        )

    # Trigger initial Gmail sync in the background so the user sees mail soon
    # after the redirect lands on /settings. Fire-and-forget — failures are
    # logged but don't block the link response.
    sync_service = getattr(request.app.state, "sync_service", None)
    if sync_service is not None:
        async def _initial_sync():
            try:
                count = await sync_service.sync_account(
                    account_id=account.id,
                    user_id=user["id"],
                    trace_id=trace_id,
                )
                if logger:
                    logger.info(
                        "initial_sync.complete",
                        account_id=account.id,
                        synced_count=count,
                    )
            except Exception as exc:  # noqa: BLE001
                if logger:
                    logger.error(
                        "initial_sync.failed",
                        account_id=account.id,
                        error=str(exc),
                    )

        asyncio.create_task(_initial_sync())
    elif logger:
        logger.warn("initial_sync.skipped", reason="sync_service not wired")

    return success_response(_serialize_account(account), trace_id)


@router.post("/accounts/linked/{account_id}/sync")
async def trigger_sync(
    request: Request,
    account_id: str,
    background_tasks: BackgroundTasks,
):
    """Manually trigger a Gmail sync for a linked account.

    The endpoint returns immediately; the actual sync runs as a FastAPI
    background task so slow Gmail pagination does not hold the client
    connection. Ownership is enforced via :func:`require_account_ownership`
    (CLAUDE.md D16 — strict per-account isolation).
    """
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    # D16 enforcement: the ownership check runs BEFORE the sync-service
    # availability check so we never leak the existence or non-existence
    # of an account that isn't ours.
    forbidden = await require_account_ownership(
        request, account_id, user["id"], trace_id
    )
    if forbidden is not None:
        return forbidden

    sync_service = getattr(request.app.state, "sync_service", None)
    if sync_service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Sync service not configured", trace_id
            ),
        )

    # Audit the action (best-effort — a broken audit store must not block).
    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is not None:
        try:
            await audit_repo.log_event(
                actor=user["id"],
                action="ACCOUNT_SYNC",
                target=account_id,
            )
        except Exception:
            pass

    sync_started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    logger = getattr(request.app.state, "logger", None)

    async def _run_sync_in_background() -> None:
        try:
            count = await sync_service.sync_account(
                account_id=account_id,
                user_id=user["id"],
                trace_id=trace_id,
            )
            if logger:
                logger.info(
                    "sync.complete",
                    service="account-link",
                    action="sync.complete",
                    trace_id=trace_id,
                    account_id=account_id,
                    user_id=user["id"],
                    synced_count=count,
                )
        except Exception as exc:  # noqa: BLE001
            if logger:
                logger.error(
                    "sync.failed",
                    service="account-link",
                    action="sync.failed",
                    trace_id=trace_id,
                    account_id=account_id,
                    user_id=user["id"],
                    error=str(exc),
                )

    background_tasks.add_task(_run_sync_in_background)

    duration_ms = round((time.monotonic() - started_monotonic) * 1000, 1)
    if logger:
        logger.info(
            "sync.triggered",
            service="account-link",
            action="sync.triggered",
            trace_id=trace_id,
            account_id=account_id,
            user_id=user["id"],
            duration_ms=duration_ms,
        )

    return success_response(
        {
            "success": True,
            "syncStartedAt": sync_started_at.isoformat(),
            "traceId": trace_id,
        },
        trace_id,
    )


@router.delete("/accounts/linked/{account_id}")
async def revoke_linked_account(request: Request, account_id: str):
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    service = getattr(request.app.state, "account_link_service", None)
    if service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Account link service not configured", trace_id
            ),
        )

    try:
        await service.revoke_account(account_id=account_id, user_id=user["id"])
    except PermissionError as e:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", str(e), trace_id),
        )

    return success_response({"success": True}, trace_id)


@router.delete("/accounts/linked/{account_id}/permanent")
async def permanently_delete_linked_account(request: Request, account_id: str):
    """Hard-delete a revoked linked account so it disappears from the
    Settings → Linked Accounts list entirely. Only allowed when the
    account is already REVOKED (which guarantees Vault cleanup ran).
    """
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    service = getattr(request.app.state, "account_link_service", None)
    if service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Account link service not configured", trace_id
            ),
        )

    try:
        await service.delete_account(account_id=account_id, user_id=user["id"])
    except PermissionError as e:
        # Collapse ownership + missing into 404 so we don't leak which
        # account IDs exist for other users.
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", str(e), trace_id),
        )
    except ValueError as e:
        return JSONResponse(
            status_code=409,
            content=error_response("ACCOUNT_NOT_REVOKED", str(e), trace_id),
        )

    # Best-effort audit log
    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is not None:
        try:
            await audit_repo.log_event(
                actor=user["id"],
                action="ACCOUNT_PERMANENT_DELETE",
                target=account_id,
            )
        except Exception:
            pass

    return success_response({"success": True}, trace_id)


def _serialize_account(account) -> dict:
    return {
        "id": account.id,
        "googleEmail": account.google_email,
        "workspaceDomain": account.workspace_domain,
        "status": account.status,
        "lastSyncAt": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "createdAt": account.created_at.isoformat() if account.created_at else None,
    }
