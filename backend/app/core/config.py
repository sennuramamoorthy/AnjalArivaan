"""Centralized application settings (12-factor, env-driven)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    All secrets must come from the environment (or HashiCorp Vault in prod).
    Never commit real values to git.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "AnjalArivaan"
    APP_ENV: Literal["dev", "test", "staging", "prod"] = "dev"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Security ---
    SECRET_KEY: str = Field(default="dev-change-me-in-prod-very-long-random-string")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MFA_ISSUER: str = "AnjalArivaan-Takshashila"

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://anjal:anjal@localhost:5432/anjalarivaan"
    DATABASE_ECHO: bool = False

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- Object storage (MinIO / S3) ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_ATTACHMENTS: str = "attachments"
    MINIO_SECURE: bool = False

    # --- Google Workspace ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/accounts/oauth/callback"
    GOOGLE_WORKSPACE_ALLOWED_DOMAIN: str = "takshashilauniv.ac.in"
    GOOGLE_PUBSUB_TOPIC: str = "projects/takshashila/topics/gmail-push"

    # --- WhatsApp BSP ---
    WHATSAPP_BSP: Literal["gupshup", "interakt", "karix", "twilio", "stub"] = "stub"
    WHATSAPP_API_BASE: str = ""
    WHATSAPP_API_KEY: str = ""

    # --- AI / LLM ---
    LLM_PROVIDER: Literal["vllm", "ollama", "stub"] = "stub"
    LLM_BASE_URL: str = "http://localhost:8080"
    LLM_MODEL: str = "mistral-small-3"
    LLM_MAX_TOKENS: int = 1024

    # --- Vector store / Search ---
    QDRANT_URL: str = "http://localhost:6333"
    OPENSEARCH_URL: str = "http://localhost:9200"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # --- Vault ---
    VAULT_URL: str = "http://localhost:8200"
    VAULT_TOKEN: str = ""
    VAULT_MOUNT_POINT: str = "secret"
    VAULT_PROVIDER: Literal["hashicorp", "stub"] = "stub"

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://anjalarivaan.takshashilauniv.ac.in",
    ]

    # --- Compliance ---
    DPDP_DATA_RESIDENCY: Literal["IN"] = "IN"
    AUDIT_WORM_BUCKET: str = "audit-worm"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings accessor (always use this; never instantiate Settings directly)."""
    return Settings()


settings = get_settings()
