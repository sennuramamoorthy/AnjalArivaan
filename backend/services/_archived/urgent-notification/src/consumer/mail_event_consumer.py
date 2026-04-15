"""
MailEventConsumer — Kafka consumer loop for 'mail-events' topic.

Processes events with event_type == 'mail.new' and delegates to
UrgencyNotificationService.

process_message() is kept pure / testable without a real Kafka broker.
"""

import asyncio
import json
import logging

from src.services.notification_service import UrgencyNotificationService

logger = logging.getLogger(__name__)

MAIL_EVENTS_TOPIC = "mail-events"
EXPECTED_EVENT_TYPE = "mail.new"

# Required keys for a valid mail.new event
_REQUIRED_KEYS = {"event_type", "account_id", "user_id", "mail"}


class MailEventConsumer:
    def __init__(
        self,
        notification_service: UrgencyNotificationService,
        kafka_brokers: str,
        group_id: str = "urgent-notification-group",
    ):
        self._notification_service = notification_service
        self._kafka_brokers = kafka_brokers
        self._group_id = group_id

    async def process_message(self, event: dict) -> None:
        """
        Process a single decoded event dict.

        Testable without Kafka — accepts a plain dict.
        Silently ignores unknown event types.
        Logs and swallows malformed events (no crash).
        """
        event_type = event.get("event_type")

        if event_type != EXPECTED_EVENT_TYPE:
            if event_type:
                logger.debug(
                    "Ignoring event with unknown type",
                    extra={"event_type": event_type},
                )
            return

        # Validate required keys before delegating
        missing = _REQUIRED_KEYS - event.keys()
        if missing or not isinstance(event.get("mail"), dict) or not event["mail"].get("id"):
            logger.warning(
                "Malformed mail.new event received; skipping",
                extra={"missing_keys": list(missing), "event_keys": list(event.keys())},
            )
            return

        trace_id: str = event.get("trace_id", "")

        try:
            await self._notification_service.process_new_mail(
                mail=event["mail"],
                account_id=event["account_id"],
                user_id=event["user_id"],
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.error(
                "Unhandled error processing mail.new event",
                extra={
                    "mail_id": event["mail"].get("id"),
                    "account_id": event.get("account_id"),
                    "trace_id": trace_id,
                    "error": str(exc),
                },
                exc_info=True,
            )

    async def start(self) -> None:
        """
        Start consuming from the mail-events topic. Runs forever.
        Used in production — not called in tests.
        """
        from confluent_kafka import Consumer, KafkaError

        consumer = Consumer(
            {
                "bootstrap.servers": self._kafka_brokers,
                "group.id": self._group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        consumer.subscribe([MAIL_EVENTS_TOPIC])
        logger.info(
            "MailEventConsumer started",
            extra={"topic": MAIL_EVENTS_TOPIC, "group_id": self._group_id},
        )

        try:
            while True:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(
                        "Kafka consumer error",
                        extra={"error": str(msg.error())},
                    )
                    continue

                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Failed to decode Kafka message as JSON",
                        extra={"error": str(exc), "raw": msg.value()[:200]},
                    )
                    continue

                await self.process_message(event)

        finally:
            consumer.close()
            logger.info("MailEventConsumer stopped")
