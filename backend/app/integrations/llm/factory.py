"""Factory — picks an LLM implementation from config."""
from app.core.config import settings
from app.integrations.llm.base import LLMClient
from app.integrations.llm.stub import StubLLMClient
from app.integrations.llm.vllm import VLLMClient


def get_llm_client() -> LLMClient:
    if settings.LLM_PROVIDER == "vllm":
        return VLLMClient()
    return StubLLMClient(model_id=settings.LLM_MODEL or "stub-model-1")
