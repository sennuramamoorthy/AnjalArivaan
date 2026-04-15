"""
TDD: tests for ContextAssembler.assemble()
Write these tests FIRST — run before any implementation exists.
"""
import pytest

from src.adapters.vector_store.mock_vector_store_adapter import MockVectorStoreAdapter
from src.domain.task import AITask, SummarizeRequest, DailyBriefingRequest
from src.repositories.in_memory_role_template_repo import InMemoryRoleTemplateRepo
from src.services.context_assembler import ContextAssembler

MOCK_ROLE_TEMPLATE = {
    "designation": "VC",
    "persona_prompt": "You are the Vice Chancellor of Takshashila University...",
    "kpis": ["regulatory compliance", "academic excellence"],
    "urgency_rules_ref": "rules-vc-001",
}

MOCK_THREAD = [
    {
        "from": "secretary@ugc.gov.in",
        "subject": "Annual Report Deadline",
        "body": "Please submit the report by April 15, 2026.",
        "received_at": "2026-04-12T09:00:00Z",
    },
]

MOCK_CHUNKS = [
    {"chunk_id": "c1", "text": "UGC requires annual submission.", "score": 0.92, "source_mail_id": "m1"},
    {"chunk_id": "c2", "text": "Last year's report was submitted on April 10.", "score": 0.85, "source_mail_id": "m2"},
]


def _make_assembler(chunks_by_collection=None):
    repo = InMemoryRoleTemplateRepo()
    repo.seed("user-vc-01", MOCK_ROLE_TEMPLATE)
    vector_store = MockVectorStoreAdapter(results_per_collection=chunks_by_collection or {})
    return ContextAssembler(role_template_repo=repo, vector_store=vector_store, top_k=5)


def _make_summarize_request(account_id="acct-001", user_id="user-vc-01"):
    return SummarizeRequest(
        account_id=account_id,
        user_id=user_id,
        trace_id="trace-001",
        thread_id="thread-001",
        messages=MOCK_THREAD,
    )


# ---------------------------------------------------------------------------
# 1. Assembles context with role template
# ---------------------------------------------------------------------------
async def test_assembles_context_with_role_template():
    assembler = _make_assembler()
    request = _make_summarize_request()
    ctx = await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    assert ctx.role_template == MOCK_ROLE_TEMPLATE
    assert ctx.account_id == "acct-001"
    assert ctx.user_id == "user-vc-01"
    assert ctx.task == AITask.SUMMARIZE_THREAD


# ---------------------------------------------------------------------------
# 2. Queries Qdrant with correct account namespace
# ---------------------------------------------------------------------------
async def test_queries_qdrant_with_correct_account_namespace():
    vector_store = MockVectorStoreAdapter(results_per_collection={"acct-001": MOCK_CHUNKS})
    repo = InMemoryRoleTemplateRepo({"user-vc-01": MOCK_ROLE_TEMPLATE})
    assembler = ContextAssembler(repo, vector_store, top_k=5)

    request = _make_summarize_request(account_id="acct-001")
    await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    assert len(vector_store.search_calls) == 1
    assert vector_store.search_calls[0]["collection"] == "acct-001"


# ---------------------------------------------------------------------------
# 3. Does NOT leak chunks from another account (D16 isolation)
# ---------------------------------------------------------------------------
async def test_does_not_leak_chunks_from_other_account():
    # Seed chunks ONLY for acct-999, not for acct-001
    vector_store = MockVectorStoreAdapter(results_per_collection={"acct-999": MOCK_CHUNKS})
    repo = InMemoryRoleTemplateRepo({"user-vc-01": MOCK_ROLE_TEMPLATE})
    assembler = ContextAssembler(repo, vector_store, top_k=5)

    request = _make_summarize_request(account_id="acct-001")
    ctx = await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    # acct-001 has no chunks — must not receive acct-999's chunks
    assert ctx.retrieved_chunks == []
    # Collection queried must be acct-001, never acct-999
    assert vector_store.search_calls[0]["collection"] == "acct-001"
    assert vector_store.search_calls[0]["collection"] != "acct-999"


# ---------------------------------------------------------------------------
# 4. Includes top_k chunks in context
# ---------------------------------------------------------------------------
async def test_includes_top_k_chunks_in_context():
    many_chunks = [
        {"chunk_id": f"c{i}", "text": f"chunk {i}", "score": 0.9 - i * 0.01, "source_mail_id": None}
        for i in range(10)
    ]
    vector_store = MockVectorStoreAdapter(results_per_collection={"acct-001": many_chunks[:5]})
    repo = InMemoryRoleTemplateRepo({"user-vc-01": MOCK_ROLE_TEMPLATE})
    assembler = ContextAssembler(repo, vector_store, top_k=5)

    request = _make_summarize_request()
    ctx = await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    # The mock returns 5 chunks; they must all be present in context
    assert len(ctx.retrieved_chunks) == 5
    assert ctx.retrieved_chunks[0].chunk_id == "c0"


# ---------------------------------------------------------------------------
# 5. Formats thread messages as primary content
# ---------------------------------------------------------------------------
async def test_formats_thread_messages_as_primary_content():
    assembler = _make_assembler()
    request = _make_summarize_request()
    ctx = await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    assert "secretary@ugc.gov.in" in ctx.primary_content
    assert "Annual Report Deadline" in ctx.primary_content
    assert "April 15, 2026" in ctx.primary_content


# ---------------------------------------------------------------------------
# 6. Handles empty Qdrant results gracefully
# ---------------------------------------------------------------------------
async def test_handles_empty_qdrant_results_gracefully():
    assembler = _make_assembler(chunks_by_collection={})  # no chunks for any collection
    request = _make_summarize_request()
    ctx = await assembler.assemble(request, AITask.SUMMARIZE_THREAD)

    assert ctx.retrieved_chunks == []
    assert ctx.primary_content != ""  # primary content still populated
