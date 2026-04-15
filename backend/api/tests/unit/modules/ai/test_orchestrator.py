"""
TDD: tests for AIOrchestrator
"""
import json
import pytest

from src.modules.ai.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.modules.ai.adapters.vector_store.mock_vector_store_adapter import MockVectorStoreAdapter
from src.modules.ai.adapters.template_store.mock_template_store import MockTemplateStore
from src.modules.ai.domain.task import (
    AITask,
    SummarizeRequest,
    DraftReplyRequest,
    DailyBriefingRequest,
)
from src.modules.ai.repositories.in_memory_role_template_repo import InMemoryRoleTemplateRepo
from src.modules.ai.services.context_assembler import ContextAssembler
from src.modules.ai.services.guardrails import InputGuardrails, OutputGuardrails
from src.modules.ai.services.orchestrator import AIOrchestrator

MOCK_ROLE_TEMPLATE = {
    "designation": "Registrar",
    "persona_prompt": "You are the Registrar of Takshashila University.",
    "kpis": ["compliance", "records management"],
    "urgency_rules_ref": "rules-reg-001",
}

MOCK_THREAD = [
    {
        "from": "admin@aicte-india.org",
        "subject": "Accreditation Documents",
        "body": "Please submit accreditation documents by April 20.",
        "received_at": "2026-04-12T10:00:00Z",
    }
]

MOCK_CHUNKS = [
    {"chunk_id": "c1", "text": "Accreditation guidelines v3.2", "score": 0.88, "source_mail_id": "m10"},
]


class _CapturingLogger:
    """Simple logger stub that records all info() calls for assertions."""

    def __init__(self, log_store=None):
        self.entries: list[dict] = log_store if log_store is not None else []

    def info(self, message: str, **kwargs):
        self.entries.append({"message": message, **kwargs})

    def debug(self, message: str, **kwargs):
        pass

    def warn(self, message: str, **kwargs):
        pass

    def error(self, message: str, **kwargs):
        pass

    def child(self, **kwargs):
        return self


def _make_orchestrator(
    canned_response="Mock AI response",
    chunks_by_collection=None,
    captured_logs=None,
):
    repo = InMemoryRoleTemplateRepo({"user-reg-01": MOCK_ROLE_TEMPLATE})
    vector_store = MockVectorStoreAdapter(results_per_collection=chunks_by_collection or {})
    assembler = ContextAssembler(repo, vector_store, top_k=5)
    llm = MockLLMAdapter(canned_response)
    templates = MockTemplateStore()
    logger = _CapturingLogger(captured_logs)
    return AIOrchestrator(
        context_assembler=assembler,
        llm_adapter=llm,
        template_store=templates,
        input_guardrails=InputGuardrails(),
        output_guardrails=OutputGuardrails(),
        logger=logger,
        model_id="llama-3.1-8b",
    ), llm, templates, logger


def _summarize_req(account_id="acct-001", user_id="user-reg-01"):
    return SummarizeRequest(
        account_id=account_id,
        user_id=user_id,
        trace_id="trace-abc",
        thread_id="thread-xyz",
        messages=MOCK_THREAD,
        instructions="Be brief.",
    )


def _draft_req(account_id="acct-001", user_id="user-reg-01"):
    return DraftReplyRequest(
        account_id=account_id,
        user_id=user_id,
        trace_id="trace-def",
        thread_id="thread-xyz",
        messages=MOCK_THREAD,
        instructions="Formal tone.",
    )


def _briefing_req(account_id="acct-001", user_id="user-reg-01"):
    return DailyBriefingRequest(
        account_id=account_id,
        user_id=user_id,
        trace_id="trace-ghi",
        urgent_mails=[{"from": "ugc.gov.in", "subject": "Urgent", "deadline": "2026-04-15"}],
        todays_meetings=[{"title": "Senate", "start_time": "09:00", "location": "Board Room"}],
        pending_tasks=[{"subject": "Submit report", "due_at": "2026-04-15", "status": "open"}],
    )


# ---------------------------------------------------------------------------
# 1. Summarize thread calls LLM with assembled prompt
# ---------------------------------------------------------------------------
async def test_summarize_thread_calls_llm_with_assembled_prompt():
    orchestrator, llm, templates, _ = _make_orchestrator()
    await orchestrator.summarize(_summarize_req())

    assert len(llm.calls) == 1
    assert len(templates.render_calls) == 1
    assert templates.render_calls[0]["template_id"] == "summarize_thread_v1"


# ---------------------------------------------------------------------------
# 2. Summarize thread returns AIResponse with all fields
# ---------------------------------------------------------------------------
async def test_summarize_thread_returns_ai_response_with_all_fields():
    orchestrator, _, _, _ = _make_orchestrator("Summary output")
    response = await orchestrator.summarize(_summarize_req())

    assert response.task == AITask.SUMMARIZE_THREAD
    assert response.output == "Summary output"
    assert response.model_id == "llama-3.1-8b"
    assert response.prompt_template_id == "summarize_thread_v1"
    assert isinstance(response.retrieved_chunk_count, int)
    assert isinstance(response.duration_ms, float)
    assert response.trace_id == "trace-abc"


# ---------------------------------------------------------------------------
# 3. Draft reply uses draft_reply template
# ---------------------------------------------------------------------------
async def test_draft_reply_uses_draft_reply_template():
    orchestrator, _, templates, _ = _make_orchestrator()
    await orchestrator.draft_reply(_draft_req())

    assert templates.render_calls[0]["template_id"] == "draft_reply_v1"


# ---------------------------------------------------------------------------
# 4. Daily briefing uses briefing template
# ---------------------------------------------------------------------------
async def test_daily_briefing_uses_briefing_template():
    orchestrator, _, templates, _ = _make_orchestrator()
    await orchestrator.daily_briefing(_briefing_req())

    assert templates.render_calls[0]["template_id"] == "daily_briefing_v1"


# ---------------------------------------------------------------------------
# 5. Orchestrator logs model_id, prompt_template_id, chunk_count
# ---------------------------------------------------------------------------
async def test_orchestrator_logs_model_id_prompt_template_id_chunk_count():
    logs: list[dict] = []
    orchestrator, _, _, logger = _make_orchestrator(
        chunks_by_collection={"acct-001": MOCK_CHUNKS},
        captured_logs=logs,
    )
    await orchestrator.summarize(_summarize_req())

    ai_log = next(e for e in logs if e.get("message") == "AI request completed")
    assert ai_log["model_id"] == "llama-3.1-8b"
    assert ai_log["prompt_template_id"] == "summarize_thread_v1"
    assert ai_log["retrieved_chunk_count"] == 1


# ---------------------------------------------------------------------------
# 6. Orchestrator logs duration_ms
# ---------------------------------------------------------------------------
async def test_orchestrator_logs_duration_ms():
    logs: list[dict] = []
    orchestrator, _, _, _ = _make_orchestrator(captured_logs=logs)
    await orchestrator.summarize(_summarize_req())

    ai_log = next(e for e in logs if e.get("message") == "AI request completed")
    assert "duration_ms" in ai_log
    assert ai_log["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# 7. Per-account isolation enforced: two different accounts use different namespaces
# ---------------------------------------------------------------------------
async def test_per_account_isolation_enforced():
    repo = InMemoryRoleTemplateRepo({
        "user-reg-01": MOCK_ROLE_TEMPLATE,
    })
    vector_store = MockVectorStoreAdapter(results_per_collection={
        "acct-001": MOCK_CHUNKS,
        "acct-002": [{"chunk_id": "cx", "text": "other account chunk", "score": 0.9, "source_mail_id": None}],
    })
    assembler = ContextAssembler(repo, vector_store, top_k=5)
    llm = MockLLMAdapter()
    logger = _CapturingLogger()
    orchestrator = AIOrchestrator(
        context_assembler=assembler,
        llm_adapter=llm,
        template_store=MockTemplateStore(),
        input_guardrails=InputGuardrails(),
        output_guardrails=OutputGuardrails(),
        logger=logger,
        model_id="llama-3.1-8b",
    )

    req1 = _summarize_req(account_id="acct-001")
    req2 = _summarize_req(account_id="acct-002")

    await orchestrator.summarize(req1)
    await orchestrator.summarize(req2)

    collections_queried = [c["collection"] for c in vector_store.search_calls]
    assert "acct-001" in collections_queried
    assert "acct-002" in collections_queried
    # Each call must use its own namespace; never cross-contaminate
    assert collections_queried[0] == "acct-001"
    assert collections_queried[1] == "acct-002"


# ---------------------------------------------------------------------------
# 8. Returns sources with response
# ---------------------------------------------------------------------------
async def test_returns_sources_with_response():
    orchestrator, _, _, _ = _make_orchestrator(
        chunks_by_collection={"acct-001": MOCK_CHUNKS}
    )
    response = await orchestrator.summarize(_summarize_req())

    assert len(response.sources) == 1
    assert response.sources[0]["chunk_id"] == "c1"
    assert response.sources[0]["text"] == "Accreditation guidelines v3.2"


# ---------------------------------------------------------------------------
# 9. Passes instructions to prompt render context
# ---------------------------------------------------------------------------
async def test_passes_instructions_to_prompt():
    orchestrator, _, templates, _ = _make_orchestrator()
    req = _summarize_req()
    req.instructions = "Highlight deadlines."
    await orchestrator.summarize(req)

    render_ctx = templates.render_calls[0]["context"]
    assert render_ctx["instructions"] == "Highlight deadlines."
