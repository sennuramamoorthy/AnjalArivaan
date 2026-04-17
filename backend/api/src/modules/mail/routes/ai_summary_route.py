"""GET /api/v1/mail/threads/{threadId}/ai-summary

Dedicated route for AI-generated thread summaries. Keeps logic out of
``ai_routes.py`` (which owns the POST /ai-draft endpoint) so the two
features can evolve independently.

Preferred backend is ``app.state.ai_summary_service`` — a thin service
that wraps an ``ILLMAdapter`` with a 24h Redis cache and role-aware
prompting. If that service is missing, we fall back to the AI
orchestrator so callers still get a summary in dev environments where
only one of the two paths is wired.

Response envelope (for PWA ``AiSummary`` type + brief ``success_response``
spec): ``{summary, modelId, cached, keyPoints, urgencyReason, generatedAt,
retrievedChunkCount}``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import error_response, success_response
from src.shared.middleware.account_ownership import require_account_ownership

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request) -> Optional[dict]:
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


def _urgency_reason(messages) -> Optional[str]:
    for m in messages:
        level = getattr(m, "urgency_level", None)
        value = getattr(level, "value", None)
        if value in ("HIGH", "CRITICAL"):
            return f"Message from {m.from_address} flagged as {value}"
    return None


# ── Route ────────────────────────────────────────────────────────────────────


@router.get("/mail/threads/{thread_id}/ai-summary")
async def ai_summary(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
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

    # D16: caller must own this linked account.
    forbidden = await require_account_ownership(
        request, accountId, user["id"], trace_id
    )
    if forbidden:
        return forbidden

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Mail service not available", trace_id
            ),
        )

    service = getattr(request.app.state, "ai_summary_service", None)
    if service is not None:
        return await _summarise_via_service(
            service=service,
            mail_repo=mail_repo,
            thread_id=thread_id,
            account_id=accountId,
            user_id=user["id"],
            trace_id=trace_id,
        )

    # Fallback: use the legacy orchestrator path. Some deployments still
    # only wire the orchestrator (full RAG); the contract below is
    # intentionally identical.
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "AI service not available", trace_id
            ),
        )

    return await _summarise_via_orchestrator(
        orchestrator=orchestrator,
        mail_repo=mail_repo,
        thread_id=thread_id,
        account_id=accountId,
        user_id=user["id"],
        trace_id=trace_id,
    )


# ── Backends ─────────────────────────────────────────────────────────────────


async def _summarise_via_service(
    *,
    service,
    mail_repo,
    thread_id: str,
    account_id: str,
    user_id: str,
    trace_id: str,
):
    result = await service.summarise(
        thread_id=thread_id,
        account_id=account_id,
        user_id=user_id,
        trace_id=trace_id,
    )
    if result is None:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "NOT_FOUND", f"Thread {thread_id} not found", trace_id
            ),
        )

    # Compute urgencyReason from the raw thread (service already loaded
    # it once; one extra cheap call keeps the service's contract narrow).
    msgs = await mail_repo.find_thread(thread_id, account_id)

    return success_response(
        {
            "summary": result.summary,
            "modelId": result.model_id,
            "cached": result.cached,
            "keyPoints": result.key_points,
            "urgencyReason": _urgency_reason(msgs),
            "generatedAt": result.generated_at,
            "retrievedChunkCount": result.retrieved_chunk_count,
        },
        trace_id,
    )


async def _summarise_via_orchestrator(
    *,
    orchestrator,
    mail_repo,
    thread_id: str,
    account_id: str,
    user_id: str,
    trace_id: str,
):
    msgs = await mail_repo.find_thread(thread_id, account_id)
    if not msgs:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "NOT_FOUND", f"Thread {thread_id} not found", trace_id
            ),
        )

    from src.modules.ai.domain.task import SummarizeRequest

    req = SummarizeRequest(
        account_id=account_id,
        user_id=user_id,
        trace_id=trace_id,
        thread_id=thread_id,
        messages=[
            {
                "from": m.from_address,
                "subject": m.subject,
                "body": m.body_text,
                "received_at": m.received_at.isoformat(),
            }
            for m in msgs
        ],
    )
    response = await orchestrator.summarize(req)

    lines = [ln for ln in response.output.strip().split("\n") if ln.strip()]
    summary = lines[0] if lines else response.output
    key_points = [ln.lstrip("-•* ").strip() for ln in lines[1:]]

    return success_response(
        {
            "summary": summary,
            "modelId": response.model_id,
            "cached": False,
            "keyPoints": key_points,
            "urgencyReason": _urgency_reason(msgs),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "retrievedChunkCount": response.retrieved_chunk_count,
        },
        trace_id,
    )
