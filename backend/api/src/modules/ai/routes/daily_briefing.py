import asyncio
import time
import uuid
from datetime import date, datetime, timezone
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


async def _load_meetings(
    calendar_service,
    *,
    account_id: str,
    user_id: str,
    today: date,
    logger,
    trace_id: str,
) -> list[dict]:
    """Pull today's events through the ICalendarService port.

    Returns [] and logs a warn if no adapter is registered; this keeps the
    briefing serviceable while Google Calendar wiring is still in flight.
    """
    if calendar_service is None:
        if logger is not None:
            logger.warn(
                "daily_briefing.calendar_service_unavailable",
                trace_id=trace_id,
                account_id=account_id,
            )
        return []
    try:
        events = await calendar_service.list_events_for_day(
            account_id, user_id, today
        )
    except Exception as e:
        if logger is not None:
            logger.error(
                "daily_briefing.calendar_fetch_failed",
                trace_id=trace_id,
                account_id=account_id,
                error=e,
            )
        return []

    return [
        {
            "id": e.id,
            "title": e.title,
            "start": e.start.isoformat() if e.start else None,
            "end": e.end.isoformat() if e.end else None,
            "location": e.location,
            "attendees": list(e.attendees or []),
        }
        for e in events
    ]


async def _load_tasks(
    task_repo,
    *,
    user_id: str,
    logger,
    trace_id: str,
) -> list[dict]:
    """Pull pending tasks through the ITaskRepository port."""
    if task_repo is None:
        if logger is not None:
            logger.warn(
                "daily_briefing.task_repo_unavailable",
                trace_id=trace_id,
                user_id=user_id,
            )
        return []
    try:
        tasks = await task_repo.list_pending_for_user(user_id)
    except Exception as e:
        if logger is not None:
            logger.error(
                "daily_briefing.task_fetch_failed",
                trace_id=trace_id,
                user_id=user_id,
                error=e,
            )
        return []

    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "assigned_to": t.assigned_to,
            "source_mail_id": t.source_mail_id,
        }
        for t in tasks
    ]


@router.get("/briefing/daily")
async def get_daily_briefing(
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """GET endpoint for the frontend daily briefing page.

    Loads urgent mails, today's calendar events, and pending tasks in
    parallel, then delegates to the AI orchestrator.
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

    logger = getattr(request.app.state, "logger", None)
    calendar_service = getattr(request.app.state, "calendar_service", None)
    task_repo = getattr(request.app.state, "task_repo", None)

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

    # Fan-out calendar + task loads in parallel.
    today = datetime.now(timezone.utc).date()
    t0 = time.monotonic()
    todays_meetings, pending_tasks = await asyncio.gather(
        _load_meetings(
            calendar_service,
            account_id=accountId,
            user_id=user["id"],
            today=today,
            logger=logger,
            trace_id=trace_id,
        ),
        _load_tasks(
            task_repo,
            user_id=user["id"],
            logger=logger,
            trace_id=trace_id,
        ),
    )
    context_duration_ms = round((time.monotonic() - t0) * 1000, 1)

    if logger is not None:
        logger.info(
            "daily_briefing.context_loaded",
            trace_id=trace_id,
            account_id=accountId,
            user_id=user["id"],
            meeting_count=len(todays_meetings),
            task_count=len(pending_tasks),
            urgent_mail_count=len(urgent_mails),
            duration_ms=context_duration_ms,
        )

    req = DailyBriefingRequest(
        account_id=accountId,
        user_id=user["id"],
        trace_id=trace_id,
        urgent_mails=urgent_mails,
        todays_meetings=todays_meetings,
        pending_tasks=pending_tasks,
    )

    response = await orchestrator.daily_briefing(req)

    return success_response(
        {
            "content": response.output,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        trace_id,
    )
