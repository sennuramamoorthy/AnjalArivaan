from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # vLLM
    vllm_base_url: str = Field(default="http://localhost:8000", alias="VLLM_BASE_URL")
    vllm_model_id: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", alias="VLLM_MODEL_ID")
    vllm_timeout_seconds: float = Field(default=120.0, alias="VLLM_TIMEOUT_SECONDS")

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")

    # Embedding service (for Qdrant search path)
    embedding_service_url: str = Field(default="http://localhost:8001", alias="EMBEDDING_SERVICE_URL")

    # Postgres
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/anjal", alias="DATABASE_URL")

    # Service
    service_name: str = Field(default="ai-orchestrator", alias="SERVICE_NAME")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Guardrails
    max_input_chars: int = Field(default=150_000, alias="MAX_INPUT_CHARS")
    max_output_chars: int = Field(default=10_000, alias="MAX_OUTPUT_CHARS")

    # Context assembly
    qdrant_top_k: int = Field(default=5, alias="QDRANT_TOP_K")
    qdrant_score_threshold: float = Field(default=0.7, alias="QDRANT_SCORE_THRESHOLD")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
