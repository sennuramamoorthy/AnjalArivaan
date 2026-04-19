"""Mail service tests."""
from datetime import datetime, timezone

import pytest

from app.domain.schemas.mail import MailIngestPayload
from app.repositories.mail import MailMessageRepository
from app.services.mail_service import MailService


@pytest.fixture
def svc(db):
    return MailService(MailMessageRepository(db))


def _payload(**overrides):
    defaults = dict(
        gmail_msg_id="gm_1",
        thread_id="th_1",
        from_address="secretary@ugc.gov.in",
        to_addresses=["vc@takshashilauniv.ac.in"],
        subject="AQAR Reminder",
        snippet="...",
        body_text="Kindly submit.",
        received_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return MailIngestPayload(**defaults)


@pytest.mark.asyncio
async def test_ingest_stores_message(svc):
    mail = await svc.ingest(account_id=1, payload=_payload())
    assert mail.id is not None
    assert mail.owner_account_id == 1
    assert mail.from_address == "secretary@ugc.gov.in"


@pytest.mark.asyncio
async def test_ingest_is_idempotent(svc):
    m1 = await svc.ingest(account_id=1, payload=_payload())
    m2 = await svc.ingest(account_id=1, payload=_payload())
    assert m1.id == m2.id


@pytest.mark.asyncio
async def test_thread_retrieval(svc):
    await svc.ingest(
        account_id=1,
        payload=_payload(gmail_msg_id="g1", thread_id="t1"),
    )
    await svc.ingest(
        account_id=1,
        payload=_payload(gmail_msg_id="g2", thread_id="t1"),
    )
    thread = svc.get_thread(1, "t1")
    assert len(thread) == 2


@pytest.mark.asyncio
async def test_per_account_isolation(svc):
    await svc.ingest(account_id=1, payload=_payload(gmail_msg_id="acct1_msg"))
    await svc.ingest(account_id=2, payload=_payload(gmail_msg_id="acct2_msg"))
    assert len(svc.list_inbox(1)) == 1
    assert len(svc.list_inbox(2)) == 1
