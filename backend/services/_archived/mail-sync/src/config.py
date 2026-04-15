"""
Pydantic settings for the Mail Sync service.

All values are read from environment variables (or a .env file during development).
No credentials are hardcoded here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MAIL_SYNC_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Service identity
    service_name: str = "mail-sync"
    log_level: str = "info"

    # Postgres
    postgres_url: str = "postgresql://anjal:anjal@localhost:5432/anjal"

    # Kafka / Redpanda
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_mail_events_topic: str = "mail-events"
    kafka_attachment_events_topic: str = "attachment-events"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
    minio_attachments_bucket: str = "attachments"

    # Account-Link token broker (internal mTLS URL)
    token_broker_url: str = "http://account-link:3001"

    # Pub/Sub
    pubsub_subscription: str = ""


settings = Settings()
