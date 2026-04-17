"""Tests for AiSummaryService.

TDD: written before the service was fleshed out. Uses the MockLLMAdapter
(deterministic) + an in-memory mail repo. No I/O outside the process —
D2 can't be violated in these tests.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from src.modules.ai.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.modules.ai.services.ai_summary_service import AiSummaryService
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import (
    InMemoryMailRepository,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mail(
    *,
    thread_id: str = "t-1",
    gmail_msg_id: str = "gm-1",
    id: str = "m-1",
    account_id: str = "acc-1",
    from_address: str = "alice@example.com",
    subject: str = "Hello",
    body_text: str = "Body",
    minutes: int = 0,
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
        received_at=datetime(2026, 4, 14, 10, minutes, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=UrgencyLevel.NONE,
        urgency_score=0.0,
        is_read=False,
    )


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value
        self.ttls[key] = ttl


class _CapturingLogger:
    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    def info(self, message: str, **kwargs):
        self.events.append(("info", message, kwargs))

    def warn(self, message: str, **kwargs):
        self.events.append(("warn", message, kwargs))

    def error(self, message: str, **kwargs):
        self.events.append(("error", message, kwargs))


def _seed(repo: InMemoryMailRepository, *mails: MailMessage):
    for m in mails:
        asyncio.get_event_loop().run_until_complete(repo.save(m))


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_none_when_thread_is_empty():
    repo = InMemoryMailRepository()
    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        model_id="mock-llm-v1",
    )

    result = await svc.summarise(
        thread_id="missing",
        account_id="acc-1",
        user_id="user-1",
        trace_id="trace-1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_summary_with_key_points():
    repo = InMemoryMailRepository()
    await repo.save(
        _mail(thread_id="t-A", gmail_msg_id="gm-A1", id="m-A1", body_text="First body")
    )
    await repo.save(
        _mail(
            thread_id="t-A",
            gmail_msg_id="gm-A2",
            id="m-A2",
            from_address="bob@example.com",
            body_text="Second body",
            minutes=5,
        )
    )

    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        model_id="mock-llm-v1",
    )
    result = await svc.summarise(
        thread_id="t-A",
        account_id="acc-1",
        user_id="user-1",
        trace_id="trace-1",
    )

    assert result is not None
    assert result.cached is False
    assert result.model_id == "mock-llm-v1"
    assert result.prompt_template_id == "summarize_thread_v1"
    assert result.retrieved_chunk_count == 0
    # Headline non-empty, key points populated from bullet lines.
    assert result.summary
    assert isinstance(result.key_points, list)
    assert len(result.key_points) >= 1


@pytest.mark.asyncio
async def test_second_call_hits_redis_cache_and_skips_llm():
    repo = InMemoryMailRepository()
    await repo.save(_mail(thread_id="t-B", gmail_msg_id="gm-B", id="m-B"))

    llm = MockLLMAdapter()
    redis = _FakeRedis()
    svc = AiSummaryService(
        llm_adapter=llm,
        mail_repo=repo,
        redis_client=redis,
        model_id="mock-llm-v1",
    )

    first = await svc.summarise(
        thread_id="t-B", account_id="acc-1", user_id="u", trace_id="t",
    )
    assert first is not None and first.cached is False
    summarize_calls_after_first = sum(
        1 for c in llm.calls if c.get("op") == "summarize_thread"
    )

    second = await svc.summarise(
        thread_id="t-B", account_id="acc-1", user_id="u", trace_id="t",
    )
    assert second is not None
    assert second.cached is True
    assert second.summary == first.summary

    summarize_calls_after_second = sum(
        1 for c in llm.calls if c.get("op") == "summarize_thread"
    )
    # Cache hit: no additional LLM invocation.
    assert summarize_calls_after_second == summarize_calls_after_first


@pytest.mark.asyncio
async def test_cache_key_is_scoped_to_account_and_model():
    repo = InMemoryMailRepository()
    await repo.save(_mail(thread_id="t-C", gmail_msg_id="gm-C", id="m-C"))

    redis = _FakeRedis()
    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        redis_client=redis,
        model_id="mock-llm-v1",
    )
    await svc.summarise(
        thread_id="t-C", account_id="acc-1", user_id="u", trace_id="t",
    )

    assert len(redis.store) == 1
    key = next(iter(redis.store))
    assert "acc-1" in key
    assert "t-C" in key
    assert "mock-llm-v1" in key
    assert "summarize_thread_v1" in key
    # TTL is 24h (86_400s).
    assert redis.ttls[key] == 24 * 60 * 60


@pytest.mark.asyncio
async def test_cache_key_differs_across_accounts_same_thread_id():
    """Defence-in-depth for D16: same thread_id in two different accounts
    must produce different cache entries."""
    repo = InMemoryMailRepository()
    await repo.save(
        _mail(thread_id="t-X", gmail_msg_id="gm-X1", id="m-X1", account_id="acc-A")
    )
    await repo.save(
        _mail(thread_id="t-X", gmail_msg_id="gm-X2", id="m-X2", account_id="acc-B")
    )
    redis = _FakeRedis()
    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        redis_client=redis,
        model_id="mock-llm-v1",
    )
    await svc.summarise(thread_id="t-X", account_id="acc-A", user_id="u", trace_id="t")
    await svc.summarise(thread_id="t-X", account_id="acc-B", user_id="u", trace_id="t")
    assert len(redis.store) == 2


@pytest.mark.asyncio
async def test_logs_ai_request_with_required_fields():
    repo = InMemoryMailRepository()
    await repo.save(_mail(thread_id="t-D", gmail_msg_id="gm-D", id="m-D"))

    logger = _CapturingLogger()
    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        logger=logger,
        model_id="mock-llm-v1",
    )
    await svc.summarise(
        thread_id="t-D", account_id="acc-1", user_id="u", trace_id="trace-xyz",
    )

    completed = [e for e in logger.events if e[1] == "ai.summary.completed"]
    assert len(completed) == 1
    fields = completed[0][2]
    for required in (
        "model_id",
        "prompt_template_id",
        "retrieved_chunk_count",
        "duration_ms",
        "trace_id",
    ):
        assert required in fields, f"missing log field {required}"
    assert fields["retrieved_chunk_count"] == 0
    assert fields["trace_id"] == "trace-xyz"
    assert fields["model_id"] == "mock-llm-v1"
    assert fields["prompt_template_id"] == "summarize_thread_v1"


@pytest.mark.asyncio
async def test_role_repo_failure_does_not_break_summary():
    """If the role-template repo is down, we still produce a summary."""
    repo = InMemoryMailRepository()
    await repo.save(_mail(thread_id="t-E", gmail_msg_id="gm-E", id="m-E"))

    class ExplodingRoleRepo:
        async def get_by_user_id(self, user_id: str):
            raise RuntimeError("db down")

    svc = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=repo,
        role_template_repo=ExplodingRoleRepo(),
        model_id="mock-llm-v1",
    )
    result = await svc.summarise(
        thread_id="t-E", account_id="acc-1", user_id="u", trace_id="t",
    )
    assert result is not None
    assert result.summary
