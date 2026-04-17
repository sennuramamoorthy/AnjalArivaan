"""TDD: BriefingGeneratorService.

Covers:
  1. Lazy backfill — ``get_or_generate`` returns cached row when present,
     otherwise generates + persists.
  2. Context fan-out — the service pulls from mail/calendar/task ports
     and those values reach the prompt handed to the LLM.
  3. Logging — every generation logs user_id, account_id, briefing_date,
     model_id, duration_ms, trace_id (CLAUDE.md requirement).
  4. Graceful degradation — missing adapters yield empty lists, not an
     exception.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

import pytest

from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.in_memory_briefing_repo import (
    InMemoryBriefingRepository,
)
from src.modules.briefing.services.briefing_generator_service import (
    BriefingGeneratorService,
)


# ───────────────────────── Test doubles ─────────────────────────


class _CapturingLogger:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def info(self, message: str, **kw: Any) -> None:
        self.entries.append({"level": "info", "message": message, **kw})

    def warn(self, message: str, **kw: Any) -> None:
        self.entries.append({"level": "warn", "message": message, **kw})

    def error(self, message: str, **kw: Any) -> None:
        self.entries.append({"level": "error", "message": message, **kw})

    def child(self, **kw: Any) -> "_CapturingLogger":
        return self


class _FakeLlm:
    def __init__(self, canned: str = "Today: 2 meetings, 1 urgent.") -> None:
        self.canned = canned
        self.calls: list[dict] = []

    async def complete(self, prompt: str, **kw: Any) -> str:
        self.calls.append({"prompt": prompt, **kw})
        return self.canned


class _UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"


@dataclass
class _FakeMail:
    id: str
    subject: str
    from_address: str
    urgency_level: _UrgencyLevel
    received_at: datetime


class _FakeMailRepo:
    def __init__(self, mails: list[_FakeMail]) -> None:
        self._mails = mails

    async def list_by_account(self, account_id: str, **kw: Any):
        return self._mails, len(self._mails)


@dataclass
class _FakeEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None
    attendees: list[str] | None = None


class _FakeCalendar:
    def __init__(self, events: list[_FakeEvent]) -> None:
        self._events = events

    async def list_events_for_day(self, account_id: str, user_id: str, day: date):
        return self._events


@dataclass
class _FakeTask:
    id: str
    subject: str
    status: str
    due_at: datetime | None


class _FakeTaskRepo:
    def __init__(self, tasks: list[_FakeTask]) -> None:
        self._tasks = tasks

    async def list_open_for_user(self, user_id: str):
        return self._tasks


# ───────────────────────── Tests ─────────────────────────


def test_get_or_generate_returns_cached_when_present():
    repo = InMemoryBriefingRepository()
    llm = _FakeLlm()
    today = datetime.now(timezone.utc).date()

    cached = DailyBriefing(
        user_id="u1",
        account_id="a1",
        briefing_date=today,
        body="Cached body",
        model_id="llama",
        prompt_template_id="daily_briefing_v1",
        generated_at=datetime.now(timezone.utc),
    )
    asyncio.run(repo.upsert(cached))

    svc = BriefingGeneratorService(
        briefing_repo=repo,
        llm_adapter=llm,
        model_id="llama",
    )
    result = asyncio.run(
        svc.get_or_generate(user_id="u1", account_id="a1", trace_id="t-1")
    )
    assert result.body == "Cached body"
    # LLM never invoked when row exists — cost + latency guarantee.
    assert llm.calls == []


def test_generate_persists_and_returns_briefing():
    repo = InMemoryBriefingRepository()
    llm = _FakeLlm(canned="Briefing text")
    svc = BriefingGeneratorService(
        briefing_repo=repo, llm_adapter=llm, model_id="llama"
    )

    result = asyncio.run(
        svc.get_or_generate(user_id="u1", account_id="a1", trace_id="t-1")
    )
    assert result.body == "Briefing text"
    # Persisted — a second call hits the cache.
    llm.calls.clear()
    asyncio.run(svc.get_or_generate(user_id="u1", account_id="a1", trace_id="t-2"))
    assert llm.calls == []


def test_prompt_includes_context_from_all_adapters():
    repo = InMemoryBriefingRepository()
    llm = _FakeLlm()
    now = datetime.now(timezone.utc)
    mail_repo = _FakeMailRepo(
        [
            _FakeMail(
                id="m1",
                subject="UGC notice: deadline tomorrow",
                from_address="alerts@ugc.gov.in",
                urgency_level=_UrgencyLevel.CRITICAL,
                received_at=now,
            )
        ]
    )
    cal = _FakeCalendar(
        [
            _FakeEvent(
                id="e1",
                title="Governance Council",
                start=now,
                end=now,
                location="Boardroom",
            )
        ]
    )
    tasks = _FakeTaskRepo(
        [_FakeTask(id="t1", subject="Approve NAAC report", status="OPEN", due_at=now)]
    )

    svc = BriefingGeneratorService(
        briefing_repo=repo,
        llm_adapter=llm,
        mail_repo=mail_repo,
        calendar_service=cal,
        task_repo=tasks,
        model_id="llama",
    )
    asyncio.run(svc.generate(user_id="u1", account_id="a1", trace_id="trace-abc"))
    assert len(llm.calls) == 1
    prompt = llm.calls[0]["prompt"]
    assert "UGC notice" in prompt
    assert "Governance Council" in prompt
    assert "Approve NAAC report" in prompt
    # D22: briefing_date emitted in ISO form.
    assert "Briefing date:" in prompt


def test_logs_required_ai_fields():
    logger = _CapturingLogger()
    svc = BriefingGeneratorService(
        briefing_repo=InMemoryBriefingRepository(),
        llm_adapter=_FakeLlm(),
        logger=logger,
        model_id="llama-3.1-8b",
    )
    asyncio.run(svc.generate(user_id="u1", account_id="a1", trace_id="trace-xyz"))

    gen_logs = [e for e in logger.entries if e["message"] == "briefing.generated"]
    assert len(gen_logs) == 1
    e = gen_logs[0]
    assert e["user_id"] == "u1"
    assert e["account_id"] == "a1"
    assert e["model_id"] == "llama-3.1-8b"
    assert e["prompt_template_id"] == "daily_briefing_v1"
    assert e["trace_id"] == "trace-xyz"
    assert "duration_ms" in e
    assert "briefing_date" in e


def test_degrades_gracefully_when_adapters_missing():
    # No mail/calendar/task/travel adapters at all.
    svc = BriefingGeneratorService(
        briefing_repo=InMemoryBriefingRepository(),
        llm_adapter=_FakeLlm("ok"),
        logger=_CapturingLogger(),
        model_id="llama",
    )
    result = asyncio.run(
        svc.generate(user_id="u1", account_id="a1", trace_id="t")
    )
    assert result.body == "ok"


def test_drops_mail_older_than_24h():
    old = datetime.now(timezone.utc).replace(year=2020)
    fresh = datetime.now(timezone.utc)
    mail_repo = _FakeMailRepo(
        [
            _FakeMail(
                id="m-old",
                subject="Stale",
                from_address="x@gov.in",
                urgency_level=_UrgencyLevel.CRITICAL,
                received_at=old,
            ),
            _FakeMail(
                id="m-new",
                subject="Fresh urgent",
                from_address="x@gov.in",
                urgency_level=_UrgencyLevel.CRITICAL,
                received_at=fresh,
            ),
        ]
    )
    llm = _FakeLlm()
    svc = BriefingGeneratorService(
        briefing_repo=InMemoryBriefingRepository(),
        llm_adapter=llm,
        mail_repo=mail_repo,
        model_id="llama",
    )
    asyncio.run(svc.generate(user_id="u1", account_id="a1", trace_id="t"))
    prompt = llm.calls[0]["prompt"]
    assert "Fresh urgent" in prompt
    assert "Stale" not in prompt
