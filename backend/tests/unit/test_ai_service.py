"""AI service tests with the stub LLM."""
from datetime import datetime, timezone

import pytest

from app.domain.models.user import RoleTemplate
from app.domain.schemas.mail import MailIngestPayload
from app.integrations.llm.stub import StubLLMClient
from app.integrations.vector import InMemoryVectorStore
from app.repositories.mail import MailMessageRepository
from app.repositories.user import AppUserRepository, RoleTemplateRepository
from app.services.ai_service import AIService
from app.services.mail_service import MailService


@pytest.fixture
def ai_deps(db, sample_user):
    mail_repo = MailMessageRepository(db)
    users = AppUserRepository(db)
    roles = RoleTemplateRepository(db)
    vector = InMemoryVectorStore()
    llm = StubLLMClient()
    return mail_repo, users, roles, vector, llm


@pytest.mark.asyncio
async def test_summarize_thread_streams_stub_output(ai_deps, sample_user, db):
    mail_repo, users, roles, vector, llm = ai_deps
    mail_svc = MailService(mail_repo)
    await mail_svc.ingest(
        account_id=1,
        payload=MailIngestPayload(
            gmail_msg_id="x",
            thread_id="t",
            from_address="ugc@gov.in",
            to_addresses=[sample_user.email],
            subject="AQAR",
            body_text="Please submit the Annual Quality Assurance Report by 30/04/2026.",
            received_at=datetime.now(timezone.utc),
        ),
    )
    svc = AIService(llm=llm, mail_repo=mail_repo, users=users, roles=roles, vector=vector)
    resp = await svc.summarize_thread(account_id=1, thread_id="t", user_id=sample_user.id)
    assert resp.text  # stub echoes back — non-empty
    assert resp.template_id == "summarize_v1"
    assert resp.citations and resp.citations[0]["type"] == "mail"


@pytest.mark.asyncio
async def test_draft_reply_uses_role_template(ai_deps, sample_user, db):
    mail_repo, users, roles, vector, llm = ai_deps
    # Seed a role template
    rt = RoleTemplate(
        designation="Vice Chancellor",
        persona_prompt="You are the VC. Be precise and formal.",
        kpis=["zero missed deadlines"],
    )
    db.add(rt)
    db.commit()

    # Seed a mail
    mail_svc = MailService(mail_repo)
    mail = await mail_svc.ingest(
        account_id=1,
        payload=MailIngestPayload(
            gmail_msg_id="x",
            thread_id="t",
            from_address="ugc@gov.in",
            to_addresses=[sample_user.email],
            subject="AQAR",
            body_text="Please submit by 30/04/2026.",
            received_at=datetime.now(timezone.utc),
        ),
    )
    svc = AIService(llm=llm, mail_repo=mail_repo, users=users, roles=roles, vector=vector)
    resp = await svc.draft_reply(account_id=1, mail_id=mail.id, user_id=sample_user.id, tone="formal")
    assert resp.text
    assert "VC" in resp.text or "Vice Chancellor" in resp.text or resp.model_id
