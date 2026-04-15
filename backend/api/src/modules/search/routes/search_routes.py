"""Search routes — mail search endpoint.

Phase 1a: wraps PostgreSQL ILIKE via SearchService.
Phase 1b: will switch to OpenSearch hybrid retriever.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import error_response, success_response

router = APIRouter()


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


def _to_search_result(msg) -> dict:
    """Transform MailMessage domain object to search result dict."""
    return {
        "id": msg.id,
        "threadId": msg.thread_id,
        "from": msg.from_address,
        "subject": msg.subject,
        "preview": msg.body_text[:150] if msg.body_text else "",
        "receivedAt": msg.received_at.isoformat(),
        "isRead": msg.is_read,
        "urgencyLevel": msg.urgency_level.value,
        "hasAttachment": msg.has_attachment,
        "linkedAccountId": msg.account_id,
    }


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/search/mail")
async def search_mail(
    request: Request,
    accountId: Optional[str] = Query(None),
    q: str = Query(""),
    filter: str = Query("all"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    """Search mail for a linked account."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    if not accountId:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST", "accountId query parameter is required", trace_id
            ),
        )

    search_service = getattr(request.app.state, "search_service", None)
    if search_service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Search service not available", trace_id
            ),
        )

    result = await search_service.search_mail(
        accountId, q, filter=filter, page=page, page_size=pageSize,
    )

    results = [_to_search_result(m) for m in result["results"]]

    return success_response(
        {
            "results": results,
            "total": result["total"],
            "page": result["page"],
            "pageSize": result["pageSize"],
            "hasMore": result["hasMore"],
        },
        trace_id,
    )
