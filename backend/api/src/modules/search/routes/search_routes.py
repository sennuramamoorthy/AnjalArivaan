"""Search routes — mail search endpoints.

Two endpoints live here:

* ``GET /api/v1/search/mail`` — legacy Phase 1a Postgres-ILIKE search
  delegating to ``SearchService``.
* ``GET /api/v1/search`` — Phase 1a hybrid retriever (OpenSearch BM25 +
  Qdrant vectors, RRF merge). D16: always account-scoped; returns 404
  when the caller doesn't own the requested linked account.
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


# ── Hybrid search (BM25 + vectors, RRF merged) ──────────────────────────────


async def _owned_by_user(
    request: Request, account_id: str, user_id: str
) -> bool:
    """Return True iff ``account_id`` exists AND belongs to ``user_id``.

    Tolerates both repo styles: the real ``PostgresLinkedAccountRepository``
    exposes ``find_by_id`` returning a ``LinkedAccount`` with
    ``app_user_id``; a test double may expose ``get_by_id`` returning a
    dict with ``user_id``.
    """
    repo = getattr(request.app.state, "linked_account_repo", None)
    if repo is None:
        # Without a repo we cannot enforce ownership; fail closed (D16).
        return False
    try:
        if hasattr(repo, "find_by_id"):
            row = await repo.find_by_id(account_id)
        elif hasattr(repo, "get_by_id"):
            row = await repo.get_by_id(account_id)
        else:
            return False
    except Exception:
        return False
    if row is None:
        return False
    if isinstance(row, dict):
        owner = row.get("user_id") or row.get("app_user_id")
    else:
        owner = getattr(row, "user_id", None) or getattr(row, "app_user_id", None)
    return owner == user_id


@router.get("/search")
async def search_hybrid(
    request: Request,
    accountId: str = Query(...),
    q: str = Query(""),
    type: str = Query("all"),
    limit: int = Query(20, ge=1, le=100),
):
    """Hybrid search over mail + attachments for a single linked account."""
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    if not q or not q.strip():
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "q query parameter is required", trace_id),
        )

    if not await _owned_by_user(request, accountId, user["id"]):
        # D16 / ownership guard: collapse "unknown account" and "foreign
        # account" into a single 404 so we don't leak existence.
        return JSONResponse(
            status_code=404,
            content=error_response("ACCOUNT_NOT_FOUND", "Linked account not found", trace_id),
        )

    retriever = getattr(request.app.state, "hybrid_retriever", None)
    if retriever is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Hybrid search not configured", trace_id
            ),
        )

    try:
        results = await retriever.search(
            query=q,
            account_id=accountId,
            doc_type=type,
            limit=limit,
            trace_id=trace_id,
            user_id=user["id"],
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", str(exc), trace_id),
        )

    return success_response(
        {"results": results, "accountId": accountId, "query": q, "type": type},
        trace_id,
    )
