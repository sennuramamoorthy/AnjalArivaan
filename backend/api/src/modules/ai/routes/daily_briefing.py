import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.modules.ai.domain.task import DailyBriefingRequest
from src.shared.domain.envelope import error_response, success_response

router = APIRouter()


class DailyBriefingHttpRequest(BaseModel):
    account_id: str
    user_id: str
    urgent_mails: list[dict] = []
    todays_meetings: list[dict] = []
    pending_tasks: list[dict] = []


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
        return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
    except Exception:
        return None


@router.post("/daily-briefing")
async def daily_briefing(body: DailyBriefingHttpRequest, request: Request) -> dict:
    orchestrator = request.app.state.orchestrator
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    req = DailyBriefingRequest(trace_id=trace_id, **body.model_dump())
    response = await orchestrator.daily_briefing(req)
    return {
        "success": True,
        "data": {
            "briefing": response.output,
            "sources": response.sources,
            "model_id": response.model_id,
            "prompt_template_id": response.prompt_template_id,
            "retrieved_chunk_count": response.retrieved_chunk_count,
        },
        "meta": {"trace_id": trace_id, "duration_ms": response.duration_ms},
    }


@router.get("/briefing/daily")
async def get_daily_briefing(
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """GET endpoint for the frontend daily briefing page.

    Loads urgent mails from the mail repo, then delegates to the AI orchestrator.
    Frontend calls: GET /api/v1/briefing/daily?accountId=...
    """
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

    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "AI service not available", trace_id),
        )

    # Load urgent mails for context (optional — gracefully degrade if no mail_repo)
    urgent_mails: list[dict] = []
    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is not None:
        msgs, _ = await mail_repo.list_by_account(accountId, filter="urgent", page_size=10)
        urgent_mails = [
            {
                "id": m.id,
                "subject": m.subject,
                "from": m.from_address,
                "urgency_level": m.urgency_level.value,
                "received_at": m.received_at.isoformat(),
            }
            for m in msgs
        ]

    req = DailyBriefingRequest(
        account_id=accountId,
        user_id=user["id"],
        trace_id=trace_id,
        urgent_mails=urgent_mails,
        todays_meetings=[],  # TODO: wire Google Calendar adapter
        pending_tasks=[],    # TODO: wire task repo
    )

    response = await orchestrator.daily_briefing(req)

    return success_response(
        {
            "content": response.output,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        trace_id,
    )
