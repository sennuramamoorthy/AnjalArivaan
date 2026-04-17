"""Calendar REST routes.

``GET /api/v1/calendar/events?accountId=...&from=YYYY-MM-DD&to=YYYY-MM-DD``

Fetches events from the configured ``ICalendarService`` (Google Calendar
in prod, mock in tests). Auth required; per-account isolation enforced via
``require_account_ownership`` — foreign accounts return 404, never 403.

Date range defaults to "today" (UTC) when ``from``/``to`` are omitted so
the PWA "today" view can call the endpoint with just ``accountId``.
"""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.modules.meeting.adapters.calendar.interface import CalendarEvent
from src.shared.domain.envelope import error_response, success_response
from src.shared.middleware.account_ownership import require_account_ownership

router = APIRouter()


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


def _event_to_dict(e: CalendarEvent) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "start": e.start.isoformat() if e.start else None,
        "end": e.end.isoformat() if e.end else None,
        "location": e.location,
        "attendees": list(e.attendees or []),
    }


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


@router.get("/calendar/events")
async def list_events(
    request: Request,
    accountId: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    trace_id = _trace_id(request)
    started = time.monotonic()

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

    # Parse range. Both must be valid ISO dates if supplied.
    today = datetime.now(timezone.utc).date()
    start_day = _parse_date(from_) if from_ is not None else today
    end_day = _parse_date(to) if to is not None else start_day
    if (from_ is not None and start_day is None) or (
        to is not None and end_day is None
    ):
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST",
                "from/to must be YYYY-MM-DD",
                trace_id,
            ),
        )
    if end_day < start_day:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST", "'to' must be on or after 'from'", trace_id
            ),
        )

    # D16 ownership — foreign accounts return 404, not 403.
    forbidden = await require_account_ownership(
        request, accountId, user["id"], trace_id
    )
    if forbidden:
        return forbidden

    calendar_service = getattr(request.app.state, "calendar_service", None)
    if calendar_service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "Calendar service not available", trace_id
            ),
        )

    try:
        events = await calendar_service.list_events_for_range(
            accountId, user["id"], start_day, end_day
        )
    except Exception as e:
        logger = getattr(request.app.state, "logger", None)
        if logger is not None:
            try:
                logger.error(
                    "calendar.list_failed",
                    service="calendar",
                    trace_id=trace_id,
                    account_id=accountId,
                    error=str(e),
                )
            except Exception:
                pass
        return JSONResponse(
            status_code=502,
            content=error_response(
                "UPSTREAM_ERROR", "Calendar fetch failed", trace_id
            ),
        )

    duration_ms = round((time.monotonic() - started) * 1000, 1)
    logger = getattr(request.app.state, "logger", None)
    if logger is not None:
        try:
            logger.info(
                "calendar.list",
                service="calendar",
                trace_id=trace_id,
                account_id=accountId,
                user_id=user["id"],
                event_count=len(events),
                start=start_day.isoformat(),
                end=end_day.isoformat(),
                duration_ms=duration_ms,
            )
        except Exception:
            pass

    return success_response([_event_to_dict(e) for e in events], trace_id)
