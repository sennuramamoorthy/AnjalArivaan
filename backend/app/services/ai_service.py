"""AI orchestration: thread summarization, draft replies, briefing synthesis (PRD §3.4, §6)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from jinja2 import Template

from app.core.exceptions import NotFoundError
from app.domain.models.mail import MailMessage
from app.domain.schemas.ai import AIResponse
from app.integrations.llm.base import LLMClient, LLMMessage
from app.integrations.vector import VectorStore
from app.repositories.mail import MailMessageRepository
from app.repositories.user import AppUserRepository, RoleTemplateRepository

# ---- Jinja prompt templates (versioned) ------------------------------------
# In prod these live on disk at `prompts/` and are pinned per template_id.

SUMMARIZE_TEMPLATE = Template(
    """You are AnjalArivaan, the Smart Personal Assistant for {{ university }}.
Your user is {{ user.full_name or user.email }} ({{ user.designation }}).

Summarise the following email thread in **English** with clear prioritisation
(decisions needed, deadlines, responsible parties). Use inline citations like
[msg:<id>] pointing to the source message.

---
{% for m in thread %}
[msg:{{ m.id }}] {{ m.received_at.isoformat() }} — from {{ m.from_address }}
Subject: {{ m.subject }}
{{ m.body_text[:1200] }}
---
{% endfor %}
"""
)

DRAFT_REPLY_TEMPLATE = Template(
    """You are {{ user.full_name or user.email }} ({{ user.designation }}) at {{ university }}.
Role context: {{ role.persona_prompt if role else "Respond professionally." }}

Draft a reply to the email below. Tone: {{ tone }}. Keep it concise and actionable.
If a decision is requested, state the decision in the first paragraph.

---
From: {{ mail.from_address }}
Subject: {{ mail.subject }}
Body:
{{ mail.body_text[:2000] }}
---

Retrieved context (cite with [ctx:<id>] if used):
{% for hit in retrieved %}
  [ctx:{{ hit.id }}] {{ hit.payload.get('preview', '') }}
{% endfor %}

Signature:
{{ signature or "Regards," }}
"""
)


@dataclass
class RetrievedChunk:
    id: str
    score: float
    payload: dict


class AIService:
    """Stateless orchestrator: assembles structured prompts and calls the LLM."""

    UNIVERSITY = "Takshashila University, Tamil Nadu"

    def __init__(
        self,
        *,
        llm: LLMClient,
        mail_repo: MailMessageRepository,
        users: AppUserRepository,
        roles: RoleTemplateRepository,
        vector: VectorStore | None = None,
    ) -> None:
        self.llm = llm
        self.mail_repo = mail_repo
        self.users = users
        self.roles = roles
        self.vector = vector

    async def summarize_thread(
        self, *, account_id: int, thread_id: str, user_id: int
    ) -> AIResponse:
        thread = self.mail_repo.list_thread(account_id, thread_id)
        if not thread:
            raise NotFoundError(f"thread {thread_id} not found in account {account_id}")
        user = self.users.get_or_404(user_id)
        prompt = SUMMARIZE_TEMPLATE.render(
            university=self.UNIVERSITY, user=user, thread=thread
        )
        resp = await self.llm.complete(
            [
                LLMMessage(role="system", content="You are a careful assistant. Cite sources."),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.2,
        )
        return AIResponse(
            text=resp.text,
            citations=[{"type": "mail", "id": m.id} for m in thread],
            model_id=resp.model_id,
            template_id="summarize_v1",
            latency_ms=resp.latency_ms,
            trace_id=str(uuid4()),
        )

    async def draft_reply(
        self,
        *,
        account_id: int,
        mail_id: int,
        user_id: int,
        tone: str = "formal",
        signature_html: str | None = None,
    ) -> AIResponse:
        mail = self.mail_repo.get_or_404(mail_id)
        if mail.owner_account_id != account_id:
            raise NotFoundError(f"mail {mail_id} not in account {account_id}")
        user = self.users.get_or_404(user_id)
        role = self.roles.get_by_designation(user.designation) if user.designation else None

        retrieved: list[RetrievedChunk] = []
        if self.vector:
            # embedding omitted here for brevity — in prod we'd embed mail.subject+body
            hits = await self.vector.query(
                namespace=f"acct:{account_id}",
                query=[0.0] * 1024,  # stand-in zero vector
                top_k=5,
            )
            retrieved = [RetrievedChunk(id=h.id, score=h.score, payload=h.payload) for h in hits]

        prompt = DRAFT_REPLY_TEMPLATE.render(
            university=self.UNIVERSITY,
            user=user,
            role=role,
            mail=mail,
            tone=tone,
            retrieved=retrieved,
            signature=signature_html,
        )
        resp = await self.llm.complete(
            [
                LLMMessage(role="system", content="Draft a reply. Output email body only."),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.5,
        )
        citations = [{"type": "mail", "id": mail.id}] + [
            {"type": "ctx", "id": h.id, "score": h.score} for h in retrieved
        ]
        return AIResponse(
            text=resp.text,
            citations=citations,
            model_id=resp.model_id,
            template_id="draft_reply_v1",
            latency_ms=resp.latency_ms,
            trace_id=str(uuid4()),
        )
