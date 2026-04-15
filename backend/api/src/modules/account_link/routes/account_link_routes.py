"""Account Link routes — Google Workspace OAuth linking flow.

GET  /accounts/linked          — list linked accounts for authenticated user
POST /accounts/link/initiate   — start OAuth flow
GET  /accounts/link/callback   — Google redirects here with code + state
DELETE /accounts/linked/{id}   — revoke a linked account
"""

import asyncio
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import success_response, error_response

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

    # Trigger initial Gmail sync in the background so the user sees mail soon
    # after the redirect lands on /settings. Fire-and-forget — failures are
    # logged but don't block the link response.
    sync_service = getattr(request.app.state, "sync_service", None)
    logger = getattr(request.app.state, "logger", None)
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
async def trigger_sync(request: Request, account_id: str):
    """Manually trigger a Gmail sync for a linked account."""
    trace_id = _trace_id(request)
    user = _get_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    link_service = getattr(request.app.state, "account_link_service", None)
    sync_service = getattr(request.app.state, "sync_service", None)
    if link_service is None or sync_service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Sync service not configured", trace_id
            ),
        )

    account = await link_service._repo.find_by_id(account_id)
    if account is None or account.app_user_id != user["id"]:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", "Account not found", trace_id),
        )

    try:
        count = await sync_service.sync_account(
            account_id=account_id, user_id=user["id"], trace_id=trace_id
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content=error_response("SYNC_FAILED", f"Sync failed: {e}", trace_id),
        )

    return success_response({"syncedCount": count, "accountId": account_id}, trace_id)


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


def _serialize_account(account) -> dict:
    return {
        "id": account.id,
        "googleEmail": account.google_email,
        "workspaceDomain": account.workspace_domain,
        "status": account.status,
        "lastSyncAt": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "createdAt": account.created_at.isoformat() if account.created_at else None,
    }
