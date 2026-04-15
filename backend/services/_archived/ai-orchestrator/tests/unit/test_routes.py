"""
TDD: tests for FastAPI routes
"""
import pytest
from httpx import AsyncClient, ASGITransport

from src.app import create_app
from src.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.adapters.vector_store.mock_vector_store_adapter import MockVectorStoreAdapter
from src.adapters.template_store.mock_template_store import MockTemplateStore
from src.domain.task import AITask
from src.repositories.in_memory_role_template_repo import InMemoryRoleTemplateRepo
from src.services.context_assembler import ContextAssembler
from src.services.guardrails import InputGuardrails, OutputGuardrails
from src.services.orchestrator import AIOrchestrator
from src._logger_stub import Logger

MOCK_ROLE_TEMPLATE = {
    "designation": "Dean",
    "persona_prompt": "You are the Dean of Engineering at Takshashila University.",
    "kpis": ["academic quality"],
    "urgency_rules_ref": "rules-dean-001",
}


class _SilentLogger:
    def info(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
    def warn(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def child(self, **kw): return self


def _make_test_app(canned_response="Test AI output"):
    repo = InMemoryRoleTemplateRepo({"user-dean-01": MOCK_ROLE_TEMPLATE})
    vector_store = MockVectorStoreAdapter()
    assembler = ContextAssembler(repo, vector_store, top_k=5)
    llm = MockLLMAdapter(canned_response)
    templates = MockTemplateStore()
    logger = _SilentLogger()
    orchestrator = AIOrchestrator(
        context_assembler=assembler,
        llm_adapter=llm,
        template_store=templates,
        input_guardrails=InputGuardrails(),
        output_guardrails=OutputGuardrails(),
        logger=logger,
        model_id="llama-3.1-8b",
    )
    return create_app(orchestrator=orchestrator)


_THREAD_PAYLOAD = {
    "account_id": "acct-dean",
    "user_id": "user-dean-01",
    "thread_id": "thread-001",
    "messages": [
        {
            "from": "ugc@ugc.gov.in",
            "subject": "NAAC Visit",
            "body": "NAAC team visiting on May 1.",
            "received_at": "2026-04-12T08:00:00Z",
        }
    ],
    "instructions": "",
}

_BRIEFING_PAYLOAD = {
    "account_id": "acct-dean",
    "user_id": "user-dean-01",
    "urgent_mails": [],
    "todays_meetings": [],
    "pending_tasks": [],
}


# ---------------------------------------------------------------------------
# 1. /summarize returns 200 with output
# ---------------------------------------------------------------------------
async def test_summarize_endpoint_returns_200_with_output():
    app = _make_test_app("Summary of the email.")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/summarize", json=_THREAD_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["summary"] == "Summary of the email."


# ---------------------------------------------------------------------------
# 2. /summarize validates required fields → 422 when account_id missing
# ---------------------------------------------------------------------------
async def test_summarize_endpoint_validates_required_fields():
    app = _make_test_app()
    payload_missing_account_id = {k: v for k, v in _THREAD_PAYLOAD.items() if k != "account_id"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/summarize", json=payload_missing_account_id)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. /draft-reply returns draft
# ---------------------------------------------------------------------------
async def test_draft_reply_endpoint_returns_draft():
    app = _make_test_app("Dear Sir, Please find below our response...")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/draft-reply", json=_THREAD_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "draft" in body["data"]
    assert body["data"]["draft"] == "Dear Sir, Please find below our response..."


# ---------------------------------------------------------------------------
# 4. /daily-briefing returns briefing
# ---------------------------------------------------------------------------
async def test_daily_briefing_endpoint_returns_briefing():
    app = _make_test_app("Today's briefing: No urgent items.")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/daily-briefing", json=_BRIEFING_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "briefing" in body["data"]


# ---------------------------------------------------------------------------
# 5. All endpoints include trace_id in response meta
# ---------------------------------------------------------------------------
async def test_all_endpoints_include_trace_id_in_response():
    app = _make_test_app()
    trace_id = "my-custom-trace-id-123"
    headers = {"X-Trace-ID": trace_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/summarize", json=_THREAD_PAYLOAD, headers=headers)
        r2 = await client.post("/draft-reply", json=_THREAD_PAYLOAD, headers=headers)
        r3 = await client.post("/daily-briefing", json=_BRIEFING_PAYLOAD, headers=headers)

    for resp in [r1, r2, r3]:
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["trace_id"] == trace_id


# ---------------------------------------------------------------------------
# 6. /health returns ok
# ---------------------------------------------------------------------------
async def test_health_endpoint():
    app = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
