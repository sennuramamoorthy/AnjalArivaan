"""
Integration tests for Gmail sync — require live Gmail API credentials.
These tests are SKIPPED in CI and local unit test runs.
"""

import pytest


@pytest.mark.skip(reason="Integration test: requires real Gmail API credentials and Pub/Sub setup.")
class TestGmailSyncIntegration:

    async def test_real_gmail_list_messages(self) -> None:
        """Verify that the real GmailAdapter can list messages from a live account."""
        pass

    async def test_real_vault_token_exchange(self) -> None:
        """Verify that the real VaultAdapter exchanges a vault ref for a valid access token."""
        pass

    async def test_real_minio_upload_and_download(self) -> None:
        """Verify attachment upload/download roundtrip against a real MinIO instance."""
        pass

    async def test_real_kafka_publish(self) -> None:
        """Verify a NewMailEvent is published and consumable from the real Kafka broker."""
        pass
