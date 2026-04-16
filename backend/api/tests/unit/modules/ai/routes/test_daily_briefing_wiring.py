"""TDD: tests for daily briefing wiring of calendar_service + task_repo.

Written FIRST. The GET /api/v1/briefing/daily endpoint must:
  - Pull today's meetings from app.state.calendar_service
  - Pull pending tasks from app.state.task_repo
  - Degrade gracefully (empty list + warn log) if either adapter is missing
  - Emit a structured log including trace_id, account_id, meeting_count,
    task_count, and duration_ms
"""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.ai.domain.task import AITask, AIResponse, DailyBriefingRequest
from src.modules.meeting.adapters.calendar.interface import CalendarEvent
from src.modules.meeting.adapters.calendar.mock_adapter import MockCalendarAdapter
from src.modules.task.repositories.in_memory_task_repo import InMemoryTaskRepository
from src.modules.task.repositories.interface import Task


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "dean@t.ac.in", "role": "dean"}


class _CapturingOrchestrator:
    """Orchestrator that records the DailyBriefingRequest it was passed."""

    def __init__(self) -> None:
        self.last_request: DailyBriefingRequest | None = None

    async def daily_briefing(self, request: DailyBriefingRequest) -> AIResponse:
        self.last_request = request
        return AIResponse(
            task=AITask.DAILY_BRIEFING,
            output="Briefing text",
            sources=[],
            model_id="llama-3.1-8b",
            prompt_template_id="daily_briefing_v1",
            retrieved_chunk_count=0,
            duration_ms=10.0,
            trace_id=request.trace_id,
        )


class _CapturingLogger:
    """Records every log entry emitted at any level."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def info(self, message: str, **kwargs):
        self.entries.append({"level": "info", "message": message, **kwargs})

    def debug(self, message: str, **kwargs):
        self.entries.append({"level": "debug", "message": message, **kwargs})

    def warn(self, message: str, **kwargs):
        self.entries.append({"level": "warn", "message": message, **kwargs})

    def error(self, message: str, **kwargs):
        self.entries.append({"level": "error", "message": message, **kwargs})

    def child(self, **kwargs):
        return self


def _make_event(**over) -> CalendarEvent:
    base = dict(
        id="evt-1",
        title="Governance Council",
        start=datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc),
        location="Main Block Boardroom",
        attendees=["vc@t.ac.in"],
    )
    base.update(over)
    return CalendarEvent(**base)


def _make_task(**over) -> Task:
    base = dict(
        id="task-1",
        title="Sign off on exam schedule",
        status="PENDING",
        due_at=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        assigned_to="user-1",
        source_mail_id="m-1",
    )
    base.update(over)
    return Task(**base)


def _build_app(
    *,
    calendar_service=None,
    task_repo=None,
    orchestrator=None,
    logger=None,
):
    app = create_app(auth_service=_FakeAuthService())
    app.state.orchestrator = orchestrator or _CapturingOrchestrator()
    if calendar_service is not None:
        app.state.calendar_service = calendar_service
    if task_repo is not None:
        app.state.task_repo = task_repo
    if logger is not None:
        app.state.logger = logger
    return app


# ---------------------------------------------------------------------------
# 1. Briefing includes meetings from the calendar adapter
# ---------------------------------------------------------------------------
def test_briefing_includes_meetings_from_calendar():
    cal = MockCalendarAdapter()
    # We don't know today's date at test time; seed every possible date via a
    # wildcard: the adapter contract accepts a seed(day=...) call, but we
    # instead patch the "any day" path by seeding for every account_id key.
    # Simpler: seed for whatever date the route computes by letting the
    # adapter return events regardless of date when configured with a default.
    cal.set_default_events(
        account_id="acc-1",
        events=[_make_event(id="evt-m1", title="Finance Review")],
    )
    orchestrator = _CapturingOrchestrator()
    app = _build_app(calendar_service=cal, orchestrator=orchestrator)

    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert orchestrator.last_request is not None
    meetings = orchestrator.last_request.todays_meetings
    assert len(meetings) == 1
    assert meetings[0]["id"] == "evt-m1"
    assert meetings[0]["title"] == "Finance Review"


# ---------------------------------------------------------------------------
# 2. Briefing includes pending tasks from the task repo
# ---------------------------------------------------------------------------
def test_briefing_includes_pending_tasks():
    repo = InMemoryTaskRepository()
    import asyncio

    asyncio.run(repo.save(_make_task(id="task-x", title="Approve NAAC report")))
    orchestrator = _CapturingOrchestrator()
    app = _build_app(task_repo=repo, orchestrator=orchestrator)

    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert orchestrator.last_request is not None
    tasks = orchestrator.last_request.pending_tasks
    assert len(tasks) == 1
    assert tasks[0]["id"] == "task-x"
    assert tasks[0]["title"] == "Approve NAAC report"


# ---------------------------------------------------------------------------
# 3. Degrades gracefully when calendar_service is missing
# ---------------------------------------------------------------------------
def test_degrades_gracefully_when_calendar_missing():
    logger = _CapturingLogger()
    orchestrator = _CapturingOrchestrator()
    app = _build_app(
        calendar_service=None,
        task_repo=InMemoryTaskRepository(),
        orchestrator=orchestrator,
        logger=logger,
    )

    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert orchestrator.last_request is not None
    assert orchestrator.last_request.todays_meetings == []
    # A warning about missing calendar_service should have been emitted.
    warn_entries = [e for e in logger.entries if e["level"] == "warn"]
    assert any("calendar_service" in (e["message"] or "") for e in warn_entries)


# ---------------------------------------------------------------------------
# 4. Degrades gracefully when task_repo is missing
# ---------------------------------------------------------------------------
def test_degrades_gracefully_when_task_repo_missing():
    logger = _CapturingLogger()
    orchestrator = _CapturingOrchestrator()
    app = _build_app(
        calendar_service=MockCalendarAdapter(),
        task_repo=None,
        orchestrator=orchestrator,
        logger=logger,
    )

    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert orchestrator.last_request is not None
    assert orchestrator.last_request.pending_tasks == []
    warn_entries = [e for e in logger.entries if e["level"] == "warn"]
    assert any("task_repo" in (e["message"] or "") for e in warn_entries)


# ---------------------------------------------------------------------------
# 5. Structured log emitted with counts, trace_id, account_id, duration_ms
# ---------------------------------------------------------------------------
def test_structured_log_emitted_with_counts():
    logger = _CapturingLogger()
    cal = MockCalendarAdapter()
    cal.set_default_events(
        account_id="acc-1",
        events=[_make_event(id="e1"), _make_event(id="e2")],
    )
    repo = InMemoryTaskRepository()
    import asyncio

    asyncio.run(repo.save(_make_task(id="t1")))
    asyncio.run(repo.save(_make_task(id="t2")))
    asyncio.run(repo.save(_make_task(id="t3")))

    app = _build_app(
        calendar_service=cal,
        task_repo=repo,
        orchestrator=_CapturingOrchestrator(),
        logger=logger,
    )

    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily",
        params={"accountId": "acc-1"},
        headers={**AUTH_HEADER, "X-Trace-ID": "trace-xyz"},
    )
    assert resp.status_code == 200

    # Find the structured log entry carrying the counts
    context_logs = [
        e for e in logger.entries
        if e.get("meeting_count") is not None and e.get("task_count") is not None
    ]
    assert len(context_logs) >= 1
    log = context_logs[0]
    assert log["meeting_count"] == 2
    assert log["task_count"] == 3
    assert log["account_id"] == "acc-1"
    assert log["trace_id"] == "trace-xyz"
    assert "duration_ms" in log
