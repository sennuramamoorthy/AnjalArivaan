"""
app.py — Entry point for the Urgent Notification service.

Wires up all dependencies and starts the Kafka consumer loop.
Also exposes a minimal FastAPI health endpoint for k8s liveness probes.
"""

import asyncio
import logging
import sys

from fastapi import FastAPI
import uvicorn

from src.config import settings
from src.adapters.messaging.kafka_adapter import KafkaMessageBus
from src.adapters.whatsapp.gupshup_adapter import GupshupWhatsAppAdapter
from src.adapters.email_forward.gmail_forward_adapter import GmailForwardAdapter
from src.repositories.postgres_rule_repository import PostgresUrgencyRuleRepository
from src.services.rule_engine import UrgencyRuleEngine
from src.services.notification_service import UrgencyNotificationService
from src.consumer.mail_event_consumer import MailEventConsumer

# ---------------------------------------------------------------------------
# Structured JSON logging (CLAUDE.md requirement)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "urgent-notification", "message": "%(message)s"}',
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app (health endpoint only)
# ---------------------------------------------------------------------------

app = FastAPI(title="AnjalArivaan Urgent Notification Service", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------

def build_consumer() -> MailEventConsumer:
    rule_repo = PostgresUrgencyRuleRepository(dsn=settings.postgres_dsn)

    # UserRepository would be added here in a full implementation;
    # it needs access to the identity/account-link service DB.
    # For now we import the Postgres variant (to be implemented in the
    # identity service sprint).
    from src.repositories.in_memory_repositories import InMemoryUserRepository
    user_repo = InMemoryUserRepository()  # replaced in production by PostgresUserRepository

    whatsapp = GupshupWhatsAppAdapter(
        api_key=settings.gupshup_api_key,
        app_id=settings.gupshup_app_id,
        base_url=settings.gupshup_base_url,
    )
    email_forward = GmailForwardAdapter()
    message_bus = KafkaMessageBus(brokers=settings.kafka_brokers)

    notification_service = UrgencyNotificationService(
        rule_repo=rule_repo,
        user_repo=user_repo,
        rule_engine=UrgencyRuleEngine(),
        whatsapp_adapter=whatsapp,
        email_forward_adapter=email_forward,
        message_bus=message_bus,
    )

    return MailEventConsumer(
        notification_service=notification_service,
        kafka_brokers=settings.kafka_brokers,
        group_id=settings.kafka_group_id,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _main():
    consumer = build_consumer()
    # Run health server + consumer loop concurrently
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level=settings.log_level.lower())
    server = uvicorn.Server(config)
    await asyncio.gather(
        server.serve(),
        consumer.start(),
    )


if __name__ == "__main__":
    asyncio.run(_main())
