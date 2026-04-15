"""
Integration tests for the Kafka consumer loop.
These tests require a running Kafka broker and are skipped in CI by default.
"""

import pytest


@pytest.mark.skip(reason="Integration test — requires live Kafka broker")
async def test_consumer_roundtrip():
    """
    Publish a mail.new event to Kafka, assert that the consumer picks it up
    and publishes a mail.urgency_detected event on the same topic.

    Setup required:
      - KAFKA_BROKERS env var pointing to a live broker
      - mail-events topic pre-created
    """
    pass
