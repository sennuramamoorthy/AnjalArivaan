"""Daily briefing generation (PRD §3.11, §4.5).

Aggregates: overnight urgent mail, today's meetings, pending tasks, recent gov mail,
approaching travel. Synthesises a role-appropriate summary via the AI Orchestrator.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.events import DomainEvent, Events, bus
from app.domain.models.task import TaskState
from app.domain.schemas.ai import BriefingResponse
from app.integrations.llm.base import LLMClient, LLMMessage
from app.repositories.mail import MailMessageRepository
from app.repositories.meeting import MeetingRepository
from app.repositories.task import TaskRepository
from app.repositories.travel import TravelPlanRepository
from app.repositories.user import AppUserRepository


class BriefingService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        mail_repo: MailMessageRepository,
        meetings: MeetingRepository,
        tasks: TaskRepository,
        travel: TravelPlanRepository,
        users: AppUserRepository,
    ) -> None:
        self.llm = llm
        self.mail_repo = mail_repo
        self.meetings = meetings
        self.tasks = tasks
        self.travel = travel
        self.users = users

    async def generate(self, *, user_id: int, account_id: int, as_of: datetime | None = None) -> BriefingResponse:
        now = as_of or datetime.now(timezone.utc)
        user = self.users.get_or_404(user_id)
        window_start = now - timedelta(hours=16)
        today_end = now.replace(hour=23, minute=59)

        # 1. overnight urgent mail
        urgent_mails = [
            m for m in self.mail_repo.list_for_account(account_id, limit=100)
            if m.is_urgent and m.received_at >= window_start
        ]
        # 2. today's meetings
        todays_meetings = [
            m for m in self.meetings.list_for_account(account_id, limit=200)
            if now <= m.start_at <= today_end
        ]
        # 3. pending tasks
        pending_tasks = [
            t for t in self.tasks.list_for_assignee(user_id)
            if t.state not in (TaskState.DONE, TaskState.CANCELLED)
        ][:20]
        # 4. approaching travel
        upcoming_travel = [
            p for p in self.travel.list_for_user(user_id)
            if p.start_date >= now and p.start_date <= now + timedelta(days=7)
        ]

        sections = {
            "urgent_mail": [
                {"id": m.id, "subject": m.subject, "from": m.from_address}
                for m in urgent_mails
            ],
            "meetings_today": [
                {"id": m.id, "title": m.title, "start_at": m.start_at.isoformat()}
                for m in todays_meetings
            ],
            "pending_tasks": [
                {"id": t.id, "subject": t.subject, "state": t.state.value,
                 "due_at": t.due_at.isoformat() if t.due_at else None}
                for t in pending_tasks
            ],
            "upcoming_travel": [
                {"id": p.id, "destination": p.destination, "start_date": p.start_date.isoformat()}
                for p in upcoming_travel
            ],
        }

        # Synthesize via LLM
        prompt = f"""Daily briefing for {user.full_name or user.email} ({user.designation}).
Synthesize a crisp, prioritised briefing in English. Lead with the single most
urgent item, then meetings, then tasks, then travel.

URGENT MAIL: {sections['urgent_mail']}
MEETINGS TODAY: {sections['meetings_today']}
PENDING TASKS: {sections['pending_tasks']}
UPCOMING TRAVEL: {sections['upcoming_travel']}
"""
        resp = await self.llm.complete(
            [
                LLMMessage(role="system", content="You write concise executive briefings."),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.2,
        )

        await bus.publish(
            DomainEvent(
                name=Events.BRIEFING_GENERATED,
                payload={"user_id": user_id, "account_id": account_id},
                account_id=account_id,
            )
        )
        return BriefingResponse(
            generated_at=now.isoformat(),
            user_id=user_id,
            account_id=account_id,
            summary=resp.text,
            sections=sections,
        )
