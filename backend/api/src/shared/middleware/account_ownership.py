"""Per-user account-ownership guard (enforces CLAUDE.md D16).

A request that includes an `accountId` (a linked Google account) MUST belong
to the authenticated user. Without this check a caller with any valid JWT
could operate on another user's linked account — reading mail, drafting
replies, sending on their behalf, or listing signatures.

Usage:
    from src.shared.middleware.account_ownership import require_account_ownership

    forbidden = await require_account_ownership(request, account_id, user_id, trace_id)
    if forbidden:
        return forbidden
"""

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import error_response


async def require_account_ownership(
    request: Request,
    account_id: str,
    user_id: str,
    trace_id: str,
) -> Optional[JSONResponse]:
    """Return a 403/503/404 JSONResponse if the account is not owned by the
    user, else None to signal the caller may proceed.
    """
    linked_repo = getattr(request.app.state, "linked_account_repo", None)
    if linked_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Account service not available", trace_id
            ),
        )

    try:
        account = await linked_repo.find_by_id(account_id)
    except Exception:
        account = None

    if account is None:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", "Linked account not found", trace_id),
        )

    if getattr(account, "app_user_id", None) != user_id:
        return JSONResponse(
            status_code=403,
            content=error_response(
                "FORBIDDEN", "Account does not belong to current user", trace_id
            ),
        )

    return None
