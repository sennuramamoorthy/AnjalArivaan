"""AI routes for mail threads — summary and draft reply.

These routes bridge the mail module's thread data with the AI orchestrator.
Frontend calls:
  GET  /api/v1/mail/threads/{threadId}/ai-summary
  POST /api/v1/mail/threads/{threadId}/ai-draft
"""

import uuid
from datetime import datetime, timezone
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


def _mail_to_message_dict(msg) -> dict:
    """Convert a MailMessage domain object to the dict format expected by the AI orchestrator."""
    return {
        "from": msg.from_address,
        "subject": msg.subject,
        "body": msg.body_text,
        "received_at": msg.received_at.isoformat(),
    }


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/mail/threads/{thread_id}/ai-summary")
async def ai_summary(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Generate an AI summary for a mail thread."""
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
            content=error_response("BAD_REQUEST", "accountId query parameter is required", trace_id),
        )

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "AI service not available", trace_id),
        )

    # Load thread messages
    msgs = await mail_repo.find_thread(thread_id, accountId)
    if not msgs:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Thread {thread_id} not found", trace_id),
        )

    # Build summarize request
    from src.modules.ai.domain.task import SummarizeRequest

    summarize_req = SummarizeRequest(
        account_id=accountId,
        user_id=user["id"],
        trace_id=trace_id,
        thread_id=thread_id,
        messages=[_mail_to_message_dict(m) for m in msgs],
    )

    response = await orchestrator.summarize(summarize_req)

    # Parse summary output into structured response matching AiSummary type
    # The LLM output is a single text; we parse key_points from bullet lines
    output_lines = response.output.strip().split("\n")
    summary = output_lines[0] if output_lines else response.output
    key_points = [line.lstrip("- •").strip() for line in output_lines[1:] if line.strip()]

    # Check if any message has HIGH/CRITICAL urgency
    urgency_reason = None
    for m in msgs:
        if m.urgency_level.value in ("HIGH", "CRITICAL"):
            urgency_reason = f"Message from {m.from_address} flagged as {m.urgency_level.value}"
            break

    return success_response(
        {
            "summary": summary,
            "keyPoints": key_points,
            "urgencyReason": urgency_reason,
            "modelId": response.model_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "retrievedChunkCount": response.retrieved_chunk_count,
        },
        trace_id,
    )


@router.post("/mail/threads/{thread_id}/ai-draft")
async def ai_draft(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Generate an AI draft reply for a mail thread."""
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
            content=error_response("BAD_REQUEST", "accountId query parameter is required", trace_id),
        )

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "AI service not available", trace_id),
        )

    # Load thread messages
    msgs = await mail_repo.find_thread(thread_id, accountId)
    if not msgs:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Thread {thread_id} not found", trace_id),
        )

    # Build draft reply request
    from src.modules.ai.domain.task import DraftReplyRequest

    draft_req = DraftReplyRequest(
        account_id=accountId,
        user_id=user["id"],
        trace_id=trace_id,
        thread_id=thread_id,
        messages=[_mail_to_message_dict(m) for m in msgs],
    )

    response = await orchestrator.draft_reply(draft_req)

    return success_response(
        {
            "draftText": response.output,
            "modelId": response.model_id,
            "promptTemplateId": response.prompt_template_id,
            "retrievedChunkCount": response.retrieved_chunk_count,
            "contextSources": [
                {
                    "type": "email",
                    "id": s.get("source_mail_id", s.get("chunk_id", "")),
                    "snippet": s.get("text", "")[:100],
                }
                for s in response.sources
            ],
        },
        trace_id,
    )
