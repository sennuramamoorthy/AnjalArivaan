"""Urgent dispatch integration — rule match → WhatsApp template sent."""
from datetime import datetime, timezone

import pytest

from app.domain.models.mail import MailMessage, UrgencyRule
from app.domain.models.user import AppUser
from app.integrations.whatsapp.stub import StubWhatsAppClient
from app.repositories.mail import MailMessageRepository, UrgencyRuleRepository
from app.repositories.notification import NotificationRepository
from app.repositories.user import AppUserRepository
from app.services.urgent_service import UrgentNotificationService


@pytest.fixture
def setup(db):
    # line manager
    lm = AppUser(
        email="chancellor@takshashilauniv.ac.in",
        password_hash="h",
        full_name="Chancellor",
        designation="Chancellor",
        phone_e164="+919000000000",
    )
    db.add(lm); db.flush()
    # VC reporting to chancellor
    vc = AppUser(
        email="vc@takshashilauniv.ac.in",
        password_hash="h",
        full_name="VC",
        designation="Vice Chancellor",
        phone_e164="+919000000001",
        reporting_to_id=lm.id,
    )
    db.add(vc); db.flush()

    rule = UrgencyRule(
        role_designation="Vice Chancellor",
        name="UGC urgent",
        sender_patterns=["*.gov.in"],
        keyword_patterns=["AQAR", "submit"],
        deadline_regex=r"(\d{2}/\d{2}/\d{4})",
        action_template="urgent_gov_whatsapp_v1",
        priority=10,
        enabled=True,
        created_by=vc.id,
    )
    db.add(rule); db.commit()

    mail = MailMessage(
        owner_account_id=1,
        gmail_msg_id="g1",
        thread_id="t1",
        from_address="sec@ugc.gov.in",
        to_addresses=[vc.email],
        cc_addresses=[],
        subject="AQAR submission",
        snippet="",
        body_text="Please submit AQAR by 30/04/2026.",
        body_html="",
        received_at=datetime.now(timezone.utc),
        labels=[],
    )
    db.add(mail); db.commit()

    wa = StubWhatsAppClient()
    svc = UrgentNotificationService(
        mail_repo=MailMessageRepository(db),
        rule_repo=UrgencyRuleRepository(db),
        users=AppUserRepository(db),
        notifications=NotificationRepository(db),
        whatsapp=wa,
    )
    return svc, wa, vc, lm, mail


@pytest.mark.asyncio
async def test_match_sends_whatsapp_to_recipient_and_line_manager(setup):
    svc, wa, vc, lm, mail = setup
    decision = await svc.evaluate_and_dispatch(mail, vc)
    assert decision.matched
    assert decision.deadline == "30/04/2026"
    # One send to VC, one to Chancellor (line manager)
    recipients = {s["to"] for s in wa.sent}
    assert "+919000000001" in recipients
    assert "+919000000000" in recipients


@pytest.mark.asyncio
async def test_no_match_no_sends(setup, db):
    svc, wa, vc, lm, _ = setup
    mail = MailMessage(
        owner_account_id=1,
        gmail_msg_id="g2",
        thread_id="t2",
        from_address="newsletter@vendor.com",
        to_addresses=[vc.email],
        cc_addresses=[],
        subject="Weekly Newsletter",
        snippet="",
        body_text="Nothing urgent.",
        body_html="",
        received_at=datetime.now(timezone.utc),
        labels=[],
    )
    db.add(mail); db.commit()
    decision = await svc.evaluate_and_dispatch(mail, vc)
    assert not decision.matched
    assert wa.sent == []
