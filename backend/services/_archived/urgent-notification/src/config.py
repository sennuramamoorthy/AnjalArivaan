from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Kafka
    kafka_brokers: str = "localhost:9092"
    kafka_group_id: str = "urgent-notification-group"

    # Postgres
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/anjal"

    # Gupshup WhatsApp BSP
    gupshup_api_key: str = ""
    gupshup_app_id: str = ""
    gupshup_base_url: str = "https://api.gupshup.io/sm/api/v1"

    # Service
    service_name: str = "urgent-notification"
    log_level: str = "INFO"


settings = Settings()
