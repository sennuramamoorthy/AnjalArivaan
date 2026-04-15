"""
Tests for InMemoryMailRepository — new query methods:
list_by_account, find_by_id, find_thread, mark_read.

Written FIRST (TDD).
"""

import pytest
from datetime import datetime, timezone

from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository


def _make_mail(
    *,
    id: str = "m-1",
    account_id: str = "acc-1",
    gmail_msg_id: str = "gm-1",
    thread_id: str = "t-1",
    from_address: str = "alice@example.com",
    subject: str = "Hello",
    body_text: str = "Body text",
    received_at: datetime | None = None,
    urgency_level: UrgencyLevel = UrgencyLevel.NONE,
    is_read: bool = False,
    has_attachment: bool = False,
    labels: list[str] | None = None,
) -> MailMessage:
    return MailMessage(
        id=id,
        account_id=account_id,
        gmail_msg_id=gmail_msg_id,
        thread_id=thread_id,
        from_address=from_address,
        to_addresses=["bob@example.com"],
        cc_addresses=[],
        subject=subject,
        body_text=body_text,
        body_html="",
        received_at=received_at or datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=labels or ["INBOX"],
        has_attachment=has_attachment,
        urgency_level=urgency_level,
        urgency_score=0.0,
        is_read=is_read,
    )


@pytest.fixture
async def repo() -> InMemoryMailRepository:
    r = InMemoryMailRepository()
    # Seed with test data
    await r.save(_make_mail(id="m-1", gmail_msg_id="gm-1", subject="Budget Report", from_address="dean@takshashilauniv.ac.in"))
    await r.save(_make_mail(id="m-2", gmail_msg_id="gm-2", subject="UGC Notice", from_address="officer@ugc.gov.in", urgency_level=UrgencyLevel.CRITICAL))
    await r.save(_make_mail(id="m-3", gmail_msg_id="gm-3", subject="Lunch Plans", from_address="friend@gmail.com", is_read=True))
    await r.save(_make_mail(id="m-4", gmail_msg_id="gm-4", subject="AICTE Inspection", from_address="inspector@aicte-india.org", urgency_level=UrgencyLevel.HIGH))
    await r.save(_make_mail(id="m-5", gmail_msg_id="gm-5", account_id="acc-2", subject="Other Account", from_address="other@other.com"))
    # Thread with 3 messages
    await r.save(_make_mail(id="m-t1", gmail_msg_id="gm-t1", thread_id="thread-A", subject="Thread Subject", received_at=datetime(2026, 4, 14, 8, 0, tzinfo=timezone.utc)))
    await r.save(_make_mail(id="m-t2", gmail_msg_id="gm-t2", thread_id="thread-A", subject="Re: Thread Subject", received_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc)))
    await r.save(_make_mail(id="m-t3", gmail_msg_id="gm-t3", thread_id="thread-A", subject="Re: Thread Subject", received_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)))
    return r


class TestListByAccount:
    async def test_returns_only_matching_account(self, repo):
        msgs, total = await repo.list_by_account("acc-1")
        assert total == 7  # m-1 through m-4 + m-t1 through m-t3
        assert all(m.account_id == "acc-1" for m in msgs)

    async def test_filter_urgent(self, repo):
        msgs, total = await repo.list_by_account("acc-1", filter="urgent")
        assert total == 2
        assert all(m.urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL) for m in msgs)

    async def test_filter_unread(self, repo):
        msgs, total = await repo.list_by_account("acc-1", filter="unread")
        # m-3 is read, all others are unread → 6 unread
        assert total == 6
        assert all(not m.is_read for m in msgs)

    async def test_filter_government(self, repo):
        msgs, total = await repo.list_by_account("acc-1", filter="government")
        assert total == 1  # only ugc.gov.in
        assert msgs[0].from_address.endswith(".gov.in")

    async def test_search_matches_subject(self, repo):
        msgs, total = await repo.list_by_account("acc-1", search="budget")
        assert total == 1
        assert msgs[0].subject == "Budget Report"

    async def test_search_matches_from_address(self, repo):
        msgs, total = await repo.list_by_account("acc-1", search="ugc.gov")
        assert total == 1

    async def test_pagination(self, repo):
        msgs_p1, total = await repo.list_by_account("acc-1", page=1, page_size=3)
        msgs_p2, _ = await repo.list_by_account("acc-1", page=2, page_size=3)
        assert total == 7
        assert len(msgs_p1) == 3
        assert len(msgs_p2) == 3
        # No overlap
        ids_p1 = {m.id for m in msgs_p1}
        ids_p2 = {m.id for m in msgs_p2}
        assert ids_p1.isdisjoint(ids_p2)

    async def test_results_ordered_by_received_at_desc(self, repo):
        msgs, _ = await repo.list_by_account("acc-1")
        dates = [m.received_at for m in msgs]
        assert dates == sorted(dates, reverse=True)


class TestFindById:
    async def test_returns_message(self, repo):
        msg = await repo.find_by_id("m-1", "acc-1")
        assert msg is not None
        assert msg.id == "m-1"

    async def test_returns_none_for_unknown(self, repo):
        msg = await repo.find_by_id("nonexistent", "acc-1")
        assert msg is None

    async def test_scoped_to_account(self, repo):
        msg = await repo.find_by_id("m-5", "acc-1")
        assert msg is None  # m-5 belongs to acc-2


class TestFindThread:
    async def test_returns_all_messages_in_thread(self, repo):
        msgs = await repo.find_thread("thread-A", "acc-1")
        assert len(msgs) == 3
        assert all(m.thread_id == "thread-A" for m in msgs)

    async def test_ordered_by_received_at_asc(self, repo):
        msgs = await repo.find_thread("thread-A", "acc-1")
        dates = [m.received_at for m in msgs]
        assert dates == sorted(dates)

    async def test_returns_empty_for_unknown_thread(self, repo):
        msgs = await repo.find_thread("nonexistent", "acc-1")
        assert msgs == []


class TestMarkRead:
    async def test_marks_message_as_read(self, repo):
        assert not (await repo.find_by_id("m-1", "acc-1")).is_read
        result = await repo.mark_read("m-1", "acc-1")
        assert result is True
        assert (await repo.find_by_id("m-1", "acc-1")).is_read

    async def test_returns_false_for_unknown(self, repo):
        result = await repo.mark_read("nonexistent", "acc-1")
        assert result is False
