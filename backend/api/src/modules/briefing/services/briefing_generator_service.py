"""BriefingGeneratorService — composes and persists the daily briefing.

Responsibilities
----------------
1. Pull context (overnight urgent mail last 24h, today's calendar events,
   open tasks, upcoming travel within 7d) through the appropriate ports.
2. Render a short English-only (D22) prompt via a single-string template.
3. Hand the prompt to the shared ``ILLMAdapter`` — D2 on-prem LLM only;
   no remote providers allowed.
4. Persist the result through ``IBriefingRepository`` (body encrypted at
   rest via the project's ``EncryptedField``).
5. Emit a structured log with user_id, account_id, briefing_date,
   model_id, duration_ms, trace_id (CLAUDE.md logging requirement).

Context adapters are optional — the service degrades gracefully when any
port is missing so a partially-wired stack still serves a briefing (the
mail/task/calendar routes already use the same pattern).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.interface import IBriefingRepository


# ──────────────────────────────────────────────────────────────────────
# Ports consumed by the service. Kept as local Protocols so the service
# depends on shape, not on concrete modules — unit tests can pass any
# plain object that quacks right.
# ──────────────────────────────────────────────────────────────────────


class _MailRepoLike(Protocol):
    async def list_by_account(
        self, account_id: str, **kwargs: Any
    ) -> tuple[list[Any], int]: ...


class _CalendarServiceLike(Protocol):
    async def list_events_for_day(
        self, account_id: str, user_id: str, day: date
    ) -> list[Any]: ...


class _TaskRepoLike(Protocol):
    async def list_open_for_user(self, user_id: str) -> list[Any]: ...


class _TravelRepoLike(Protocol):
    async def list_upcoming_for_user(
        self, user_id: str, within_days: int
    ) -> list[Any]: ...


class _LlmAdapterLike(Protocol):
    async def complete(
        self, prompt: str, max_tokens: int = ..., temperature: float = ..., **kwargs: Any
    ) -> str: ...


class _LoggerLike(Protocol):
    def info(self, message: str, **kwargs: Any) -> None: ...
    def warn(self, message: str, **kwargs: Any) -> None: ...
    def error(self, message: str, **kwargs: Any) -> None: ...


# ──────────────────────────────────────────────────────────────────────
# Context assembly
# ──────────────────────────────────────────────────────────────────────


@dataclass
class _Context:
    urgent_mails: list[dict]
    todays_meetings: list[dict]
    pending_tasks: list[dict]
    upcoming_travel: list[dict]


class BriefingGeneratorService:
    """Generate + persist a user's daily briefing for one linked account.

    D22: output is English-only. D16: callers are expected to validate
    that ``account_id`` belongs to ``user_id`` before invoking — the
    service itself is account-agnostic and will happily generate a
    briefing for any (user, account) pair it is given.
    """

    PROMPT_TEMPLATE_ID = "daily_briefing_v1"

    def __init__(
        self,
        *,
        briefing_repo: IBriefingRepository,
        llm_adapter: _LlmAdapterLike,
        logger: Optional[_LoggerLike] = None,
        mail_repo: Optional[_MailRepoLike] = None,
        calendar_service: Optional[_CalendarServiceLike] = None,
        task_repo: Optional[_TaskRepoLike] = None,
        travel_repo: Optional[_TravelRepoLike] = None,
        model_id: str = "unknown",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> None:
        self._repo = briefing_repo
        self._llm = llm_adapter
        self._logger = logger
        self._mail_repo = mail_repo
        self._calendar = calendar_service
        self._tasks = task_repo
        self._travel = travel_repo
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._temperature = temperature

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    async def get_or_generate(
        self,
        *,
        user_id: str,
        account_id: str,
        trace_id: str,
        briefing_date: Optional[date] = None,
    ) -> DailyBriefing:
        """Return today's briefing, generating + persisting it on a miss."""
        day = briefing_date or datetime.now(timezone.utc).date()
        existing = await self._repo.find_for_day(
            user_id=user_id, account_id=account_id, briefing_date=day
        )
        if existing is not None:
            return existing
        return await self.generate(
            user_id=user_id,
            account_id=account_id,
            trace_id=trace_id,
            briefing_date=day,
        )

    async def generate(
        self,
        *,
        user_id: str,
        account_id: str,
        trace_id: str,
        briefing_date: Optional[date] = None,
    ) -> DailyBriefing:
        day = briefing_date or datetime.now(timezone.utc).date()
        started = time.perf_counter()

        ctx = await self._assemble_context(
            user_id=user_id, account_id=account_id, day=day, trace_id=trace_id
        )
        prompt = self._render_prompt(
            user_id=user_id,
            account_id=account_id,
            day=day,
            ctx=ctx,
        )

        body = await self._llm.complete(
            prompt=prompt,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        briefing = DailyBriefing(
            user_id=user_id,
            account_id=account_id,
            briefing_date=day,
            body=body,
            model_id=self._model_id,
            prompt_template_id=self.PROMPT_TEMPLATE_ID,
            generated_at=datetime.now(timezone.utc),
        )
        await self._repo.upsert(briefing)

        if self._logger is not None:
            # CLAUDE.md mandates model_id + prompt_template_id + duration_ms
            # + trace_id on every AI request. user_id + account_id are the
            # D16 audit trail.
            self._logger.info(
                "briefing.generated",
                user_id=user_id,
                account_id=account_id,
                briefing_date=day.isoformat(),
                model_id=self._model_id,
                prompt_template_id=self.PROMPT_TEMPLATE_ID,
                duration_ms=duration_ms,
                trace_id=trace_id,
                urgent_mail_count=len(ctx.urgent_mails),
                meeting_count=len(ctx.todays_meetings),
                task_count=len(ctx.pending_tasks),
                travel_count=len(ctx.upcoming_travel),
            )

        return briefing

    # ──────────────────────────────────────────────────────────
    # Context assembly (each source degrades independently)
    # ──────────────────────────────────────────────────────────
    async def _assemble_context(
        self, *, user_id: str, account_id: str, day: date, trace_id: str
    ) -> _Context:
        return _Context(
            urgent_mails=await self._load_urgent_mails(account_id, trace_id),
            todays_meetings=await self._load_meetings(
                account_id=account_id, user_id=user_id, day=day, trace_id=trace_id
            ),
            pending_tasks=await self._load_tasks(user_id=user_id, trace_id=trace_id),
            upcoming_travel=await self._load_travel(
                user_id=user_id, trace_id=trace_id
            ),
        )

    async def _load_urgent_mails(self, account_id: str, trace_id: str) -> list[dict]:
        if self._mail_repo is None:
            self._log_warn("briefing.mail_repo_unavailable", trace_id=trace_id)
            return []
        try:
            # Last-24h urgent mail. The mail repo exposes a urgency filter;
            # the 24h cutoff is applied here by filtering the returned rows
            # so we don't leak adapter-internal SQL into the service layer.
            msgs, _ = await self._mail_repo.list_by_account(
                account_id, filter="urgent", page_size=20
            )
        except Exception as e:
            self._log_error("briefing.mail_fetch_failed", trace_id=trace_id, error=e)
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        out: list[dict] = []
        for m in msgs:
            received_at = getattr(m, "received_at", None)
            if received_at is not None and received_at < cutoff:
                continue
            out.append(
                {
                    "id": getattr(m, "id", None),
                    "subject": getattr(m, "subject", ""),
                    "from": getattr(m, "from_address", ""),
                    "urgency_level": (
                        getattr(m, "urgency_level", None).value
                        if getattr(m, "urgency_level", None) is not None
                        and hasattr(getattr(m, "urgency_level", None), "value")
                        else str(getattr(m, "urgency_level", ""))
                    ),
                    "received_at": received_at.isoformat() if received_at else None,
                }
            )
        return out

    async def _load_meetings(
        self, *, account_id: str, user_id: str, day: date, trace_id: str
    ) -> list[dict]:
        if self._calendar is None:
            self._log_warn("briefing.calendar_service_unavailable", trace_id=trace_id)
            return []
        try:
            events = await self._calendar.list_events_for_day(account_id, user_id, day)
        except Exception as e:
            self._log_error(
                "briefing.calendar_fetch_failed", trace_id=trace_id, error=e
            )
            return []
        return [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start.isoformat() if e.start else None,
                "end": e.end.isoformat() if e.end else None,
                "location": e.location,
            }
            for e in events
        ]

    async def _load_tasks(self, *, user_id: str, trace_id: str) -> list[dict]:
        if self._tasks is None:
            self._log_warn("briefing.task_repo_unavailable", trace_id=trace_id)
            return []
        try:
            tasks = await self._tasks.list_open_for_user(user_id)
        except Exception as e:
            self._log_error("briefing.task_fetch_failed", trace_id=trace_id, error=e)
            return []
        return [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status,
                "due_at": t.due_at.isoformat() if t.due_at else None,
            }
            for t in tasks
        ]

    async def _load_travel(self, *, user_id: str, trace_id: str) -> list[dict]:
        if self._travel is None:
            # Travel-plan module is Phase 1b — absence is expected, log at debug.
            return []
        try:
            items = await self._travel.list_upcoming_for_user(user_id, 7)
        except Exception as e:
            self._log_error(
                "briefing.travel_fetch_failed", trace_id=trace_id, error=e
            )
            return []
        return [
            {
                "id": getattr(t, "id", None),
                "destination": getattr(t, "destination", ""),
                "start": getattr(t, "start_date", None).isoformat()
                if getattr(t, "start_date", None)
                else None,
                "end": getattr(t, "end_date", None).isoformat()
                if getattr(t, "end_date", None)
                else None,
            }
            for t in items
        ]

    # ──────────────────────────────────────────────────────────
    # Prompt rendering
    # ──────────────────────────────────────────────────────────
    def _render_prompt(
        self,
        *,
        user_id: str,
        account_id: str,
        day: date,
        ctx: _Context,
    ) -> str:
        # D22: English-only output even when source material is Tamil.
        lines: list[str] = [
            "You are AnjalArivaan, an assistant for Takshashila University leaders.",
            "Write a short daily briefing in English (under 200 words).",
            "Do not translate names or quote non-English text verbatim; summarize in English.",
            f"Briefing date: {day.isoformat()}",
            "",
        ]

        lines.append("### Overnight urgent mail (last 24h)")
        if not ctx.urgent_mails:
            lines.append("- (none)")
        else:
            for m in ctx.urgent_mails:
                lines.append(
                    f"- {m.get('subject', '')} — from {m.get('from', '')}"
                    f" [{m.get('urgency_level', '')}]"
                )

        lines.append("")
        lines.append("### Today's calendar")
        if not ctx.todays_meetings:
            lines.append("- (nothing scheduled)")
        else:
            for e in ctx.todays_meetings:
                lines.append(
                    f"- {e.get('start', '')}: {e.get('title', '')}"
                    f" @ {e.get('location') or 'TBD'}"
                )

        lines.append("")
        lines.append("### Open tasks")
        if not ctx.pending_tasks:
            lines.append("- (no open tasks)")
        else:
            for t in ctx.pending_tasks:
                lines.append(
                    f"- {t.get('subject', '')}"
                    f" (due {t.get('due_at') or 'no deadline'})"
                )

        lines.append("")
        lines.append("### Upcoming travel (next 7 days)")
        if not ctx.upcoming_travel:
            lines.append("- (none)")
        else:
            for t in ctx.upcoming_travel:
                lines.append(
                    f"- {t.get('destination', '')}"
                    f" {t.get('start', '')} → {t.get('end', '')}"
                )

        lines.append("")
        lines.append(
            "Produce 3-5 short bullet points calling out what needs attention today."
        )
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # Logging helpers
    # ──────────────────────────────────────────────────────────
    def _log_warn(self, message: str, **kwargs: Any) -> None:
        if self._logger is None:
            return
        try:
            self._logger.warn(message, **kwargs)
        except Exception:
            pass

    def _log_error(self, message: str, **kwargs: Any) -> None:
        if self._logger is None:
            return
        try:
            self._logger.error(message, **kwargs)
        except Exception:
            pass
