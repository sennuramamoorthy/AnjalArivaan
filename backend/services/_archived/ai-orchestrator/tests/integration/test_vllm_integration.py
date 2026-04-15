"""
Integration tests — require live vLLM and Qdrant services.
Skipped in CI / unit test runs.
"""
import pytest

from src.adapters.llm.vllm_adapter import VLLMAdapter
from src.adapters.vector_store.qdrant_adapter import QdrantAdapter
from src.config import Settings


@pytest.mark.skip(reason="requires vLLM and Qdrant — run manually against real services")
async def test_vllm_completion_returns_non_empty_text():
    settings = Settings()
    adapter = VLLMAdapter(settings)
    result = await adapter.complete(prompt="Say hello in one sentence.", max_tokens=64)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.skip(reason="requires vLLM and Qdrant — run manually against real services")
async def test_qdrant_search_returns_results():
    settings = Settings()
    adapter = QdrantAdapter(settings)
    results = await adapter.search(
        collection="test-account-001",
        query_text="UGC annual report deadline",
        top_k=3,
    )
    assert isinstance(results, list)


@pytest.mark.skip(reason="requires vLLM and Qdrant — run manually against real services")
async def test_full_orchestrator_pipeline_with_real_adapters():
    """End-to-end: real vLLM + real Qdrant + Jinja2 templates."""
    from src.adapters.template_store.jinja_template_store import JinjaTemplateStore
    from src.repositories.in_memory_role_template_repo import InMemoryRoleTemplateRepo
    from src.services.context_assembler import ContextAssembler
    from src.services.guardrails import InputGuardrails, OutputGuardrails
    from src.services.orchestrator import AIOrchestrator
    from src.domain.task import SummarizeRequest
    from src._logger_stub import get_logger

    settings = Settings()
    llm = VLLMAdapter(settings)
    vector_store = QdrantAdapter(settings)
    templates = JinjaTemplateStore()
    repo = InMemoryRoleTemplateRepo({
        "test-user": {
            "designation": "VC",
            "persona_prompt": "You are the Vice Chancellor.",
            "kpis": ["compliance"],
            "urgency_rules_ref": "rules-vc-001",
        }
    })
    assembler = ContextAssembler(repo, vector_store, top_k=3)
    logger = get_logger("ai-orchestrator-integration-test")
    orchestrator = AIOrchestrator(
        context_assembler=assembler,
        llm_adapter=llm,
        template_store=templates,
        input_guardrails=InputGuardrails(),
        output_guardrails=OutputGuardrails(),
        logger=logger,
        model_id=settings.vllm_model_id,
    )

    req = SummarizeRequest(
        account_id="test-account-001",
        user_id="test-user",
        trace_id="integration-trace-001",
        thread_id="thread-integration-001",
        messages=[{
            "from": "vc@ugc.gov.in",
            "subject": "Inspection Notice",
            "body": "An inspection will be conducted on May 5, 2026.",
            "received_at": "2026-04-12T09:00:00Z",
        }],
    )
    response = await orchestrator.summarize(req)
    assert response.output
    assert response.model_id == settings.vllm_model_id
