"""Centralised configuration via Pydantic BaseSettings.

All env vars for every module are declared here. Missing optional vars
default to safe dev values. Required vars (DATABASE_URL, etc.) will
raise a validation error at startup if absent.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────
    port: int = 4001
    log_level: str = "debug"
    service_name: str = "api"

    # ── Database ──────────────────────────────────────────────────
    database_url: str = "postgresql://anjal:anjal_dev_password@localhost:5432/anjalarivaan"

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Celery (daily briefing scheduler + worker queues) ─────────
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Push notifications (FCM HTTP v1) ──────────────────────────
    fcm_project_id: str = ""

    # ── JWT / Auth ────────────────────────────────────────────────
    jwt_private_key_path: str = "./keys/jwt_private.pem"
    jwt_public_key_path: str = "./keys/jwt_public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_ttl: int = 900        # 15 min in seconds
    jwt_refresh_token_ttl: int = 604800    # 7 days in seconds
    encryption_key: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    mfa_enabled: bool = True

    # ── Vault ─────────────────────────────────────────────────────
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "anjal-vault-dev-root"

    # ── MinIO ─────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "anjal_minio"
    minio_secret_key: str = "anjal_minio_dev_password"
    minio_secure: bool = False
    minio_bucket_attachments: str = "anjal-attachments"

    # ── AI / LLM ──────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_top_k: int = 5
    qdrant_score_threshold: float = 0.7
    vllm_base_url: str = "http://localhost:8000"
    vllm_model_id: str = "meta-llama/Llama-3.1-8B-Instruct"
    vllm_timeout_seconds: float = 120.0
    embedding_model: str = "BAAI/bge-m3"
    embedding_service_url: str = "http://localhost:8001"
    opensearch_url: str = "http://localhost:9200"
    max_input_chars: int = 150_000
    max_output_chars: int = 10_000

    # ── WhatsApp BSP ──────────────────────────────────────────────
    bsp_provider: str = "gupshup"
    bsp_api_key: str = ""
    bsp_whatsapp_number: str = ""

    # ── Google OAuth (mail-sync + account-link) ─────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/oauth/callback"
    google_allowed_domains: str = "takshashilauniv.ac.in"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Lazy singleton — avoids reading env at import time."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
