"""Unit tests for daily briefing Celery task cores.

These tests exercise the pure-Python cores in
``src.workers.tasks.daily_briefing`` without spinning up a Celery worker —
the Celery wrappers are thin shims around these cores.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.infra.logger import create_logger
from src.modules.notification.adapters.email_forward.interface import (
    IEmailForwardAdapter,
)
from src.modules.notification.adapters.push.mock_adapter import MockPushAdapter
from src.workers.tasks.daily_briefing import (
    _run_for_all_users_core,
    _send_briefing_for_user_core,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeAIResponse:
    output: str = "Good morning.\n- Urgent: 0\n- Meetings: 2"
    model_id: str = "llama-3.1-8b"
    prompt_template_id: str = "daily_briefing_v1"
    retrieved_chunk_count: int = 3


class FakeOrchestrator:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list = []

    async def daily_briefing(self, request):  # noqa: ANN001
        self.calls.append(request)
        if self.raises:
            raise self.raises
        return FakeAIResponse()


class FakeEmailForwardAdapter(IEmailForwardAdapter):
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list[dict] = []

    async def forward(self, original_mail_id, to_email, from_account_token, note):
        self.calls.append(
            {
                "original_mail_id": original_mail_id,
                "to_email": to_email,
                "from_account_token": from_account_token,
                "note": note,
            }
        )
        if self.raises:
            raise self.raises


# ---------------------------------------------------------------------------
# send_briefing_for_user_core
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_briefing_calls_orchestrator_push_and_email():
    orchestrator = FakeOrchestrator()
    push = MockPushAdapter()
    email = FakeEmailForwardAdapter()

    result = await _send_briefing_for_user_core(
        user={"id": "u-1", "email": "vc@takshashilauniv.ac.in"},
        orchestrator=orchestrator,
        push_adapter=push,
        email_forward_adapter=email,
        logger=create_logger("test"),
        trace_id="trace-1",
    )

    # orchestrator invoked with a DailyBriefingRequest
    assert len(orchestrator.calls) == 1
    req = orchestrator.calls[0]
    assert req.user_id == "u-1"
    assert req.trace_id == "trace-1"

    # push delivered with body derived from orchestrator output
    assert len(push.sent) == 1
    assert push.sent[0]["user_id"] == "u-1"
    assert push.sent[0]["title"] == "Your daily briefing"
    assert "Good morning" in push.sent[0]["body"]
    assert push.sent[0]["data"]["kind"] == "daily_briefing"

    # email forward invoked with the user's address and briefing body
    assert len(email.calls) == 1
    assert email.calls[0]["to_email"] == "vc@takshashilauniv.ac.in"
    assert "Good morning" in email.calls[0]["note"]

    assert result["push_ok"] is True
    assert result["email_ok"] is True


@pytest.mark.asyncio
async def test_send_briefing_truncates_long_body_for_push():
    orchestrator = FakeOrchestrator()
    long_output = "x" * 1000
    orchestrator.daily_briefing = lambda req: _awaitable(  # type: ignore[assignment]
        FakeAIResponse(output=long_output)
    )

    push = MockPushAdapter()
    email = FakeEmailForwardAdapter()

    await _send_briefing_for_user_core(
        user={"id": "u-1", "email": "x@y.z"},
        orchestrator=orchestrator,
        push_adapter=push,
        email_forward_adapter=email,
        logger=create_logger("test"),
        trace_id="t",
    )

    assert len(push.sent[0]["body"]) <= 260  # 240 + "..."
    assert push.sent[0]["body"].endswith("...")


@pytest.mark.asyncio
async def test_send_briefing_push_failure_does_not_break_email_delivery():
    class BrokenPush(MockPushAdapter):
        async def send(self, user_id, title, body, data=None):
            raise RuntimeError("fcm down")

    push = BrokenPush()
    email = FakeEmailForwardAdapter()

    result = await _send_briefing_for_user_core(
        user={"id": "u-1", "email": "x@y.z"},
        orchestrator=FakeOrchestrator(),
        push_adapter=push,
        email_forward_adapter=email,
        logger=create_logger("test"),
        trace_id="t",
    )

    assert result["push_ok"] is False
    assert result["email_ok"] is True
    assert len(email.calls) == 1


@pytest.mark.asyncio
async def test_send_briefing_email_failure_does_not_break_push_delivery():
    push = MockPushAdapter()
    email = FakeEmailForwardAdapter(raises=RuntimeError("smtp down"))

    result = await _send_briefing_for_user_core(
        user={"id": "u-1", "email": "x@y.z"},
        orchestrator=FakeOrchestrator(),
        push_adapter=push,
        email_forward_adapter=email,
        logger=create_logger("test"),
        trace_id="t",
    )

    assert result["push_ok"] is True
    assert result["email_ok"] is False
    assert len(push.sent) == 1


# ---------------------------------------------------------------------------
# run_for_all_users_core — fanout resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_processes_every_user():
    users = [{"id": f"u-{i}"} for i in range(4)]
    seen: list[str] = []

    async def _per_user(user):
        seen.append(user["id"])

    result = await _run_for_all_users_core(
        users=users,
        per_user=_per_user,
        logger=create_logger("test"),
        trace_id="batch",
    )

    assert seen == ["u-0", "u-1", "u-2", "u-3"]
    assert result == {"total": 4, "failed": 0}


@pytest.mark.asyncio
async def test_fanout_one_bad_user_does_not_fail_the_batch():
    users = [{"id": "good-1"}, {"id": "bad"}, {"id": "good-2"}]
    delivered: list[str] = []

    async def _per_user(user):
        if user["id"] == "bad":
            raise RuntimeError("explode")
        delivered.append(user["id"])

    result = await _run_for_all_users_core(
        users=users,
        per_user=_per_user,
        logger=create_logger("test"),
        trace_id="batch",
    )

    assert delivered == ["good-1", "good-2"]
    assert result == {"total": 3, "failed": 1}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _awaitable(value):
    return value
