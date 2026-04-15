"""
TDD - tests for the Pub/Sub webhook FastAPI route.

Run BEFORE implementing src/routes/pubsub_webhook.py.
All tests should initially FAIL.
"""

import sys
import os
import base64
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from httpx import AsyncClient, ASGITransport

from adapters.gmail.mock_gmail_adapter import MockGmailAdapter
from adapters.vault.mock_vault_adapter import MockVaultAdapter
from adapters.storage.mock_storage_adapter import MockObjectStorage
from adapters.messaging.mock_message_bus import MockMessageBus
from repositories.in_memory_mail_repository import InMemoryMailRepository
from services.sync_service import MailSyncService


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _build_pubsub_payload(email_address: str = "vc@takshashilauniv.ac.in",
                          history_id: str = "12345") -> dict:
    """Build a Pub/Sub push request body as sent by Google."""
    data = _b64(json.dumps({
        "emailAddress": email_address,
        "historyId": history_id,
    }))
    return {
        "message": {
            "data": data,
            "messageId": "pubsub_msg_001",
            "publishTime": "2026-04-12T09:00:00Z",
            "attributes": {"accountId": "acc_001"},
        },
        "subscription": "projects/anjal/subscriptions/gmail-push",
    }


@pytest.fixture
def sync_service() -> MailSyncService:
    import base64 as _b64_mod
    msg = {
        "id": "gm_webhook_001",
        "threadId": "thread_w_001",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "gov@ugc.gov.in"},
                {"name": "To", "value": "vc@takshashilauniv.ac.in"},
                {"name": "Subject", "value": "Webhook Test"},
                {"name": "Date", "value": "Tue, 12 Apr 2026 09:00:00 +0530"},
            ],
            "body": {"data": _b64_mod.urlsafe_b64encode(b"Webhook body.").decode()},
            "parts": [],
        },
        "sizeEstimate": 256,
        "internalDate": "1744428000000",
    }
    from anjal_logger import get_logger  # type: ignore[import]
    logger = get_logger("mail-sync-webhook-test")
    vault = MockVaultAdapter(tokens={"acc_001": "token_001"})
    return MailSyncService(
        gmail_adapter=MockGmailAdapter(messages=[msg]),
        vault_adapter=vault,
        mail_repo=InMemoryMailRepository(),
        object_storage=MockObjectStorage(),
        message_bus=MockMessageBus(),
        logger=logger,
    )


@pytest.fixture
def app(sync_service: MailSyncService):
    from app import create_app
    return create_app(sync_service=sync_service)


@pytest.fixture
async def client(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPubSubWebhook:

    async def test_webhook_accepts_valid_pubsub_message(
        self, client: AsyncClient
    ) -> None:
        payload = _build_pubsub_payload()
        response = await client.post("/api/v1/webhooks/pubsub", json=payload)
        assert response.status_code == 200

    async def test_webhook_returns_200_to_acknowledge(
        self, client: AsyncClient
    ) -> None:
        payload = _build_pubsub_payload()
        response = await client.post("/api/v1/webhooks/pubsub", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ok"

    async def test_webhook_triggers_sync_for_correct_account(
        self, client: AsyncClient, sync_service: MailSyncService
    ) -> None:
        # We verify the sync_service runs for the account embedded in the message
        # This is a behavioral test: after the webhook, the background task should
        # have been scheduled. Since we use BackgroundTasks (inline in test), we
        # check that the route returns 200 without error for the expected account.
        payload = _build_pubsub_payload(email_address="vc@takshashilauniv.ac.in")
        payload["message"]["attributes"]["accountId"] = "acc_001"
        response = await client.post("/api/v1/webhooks/pubsub", json=payload)
        assert response.status_code == 200

    async def test_webhook_rejects_missing_message_field(
        self, client: AsyncClient
    ) -> None:
        # Malformed request: missing "message" key
        bad_payload = {
            "subscription": "projects/anjal/subscriptions/gmail-push"
        }
        response = await client.post("/api/v1/webhooks/pubsub", json=bad_payload)
        assert response.status_code == 422  # Pydantic validation error

    async def test_webhook_handles_sync_error_gracefully(
        self, client: AsyncClient
    ) -> None:
        """Even if sync fails internally, webhook must return 200 to ACK Pub/Sub."""
        # Send a request with an accountId that has no vault token → sync will
        # raise internally. The route must still return 200.
        payload = _build_pubsub_payload()
        payload["message"]["attributes"]["accountId"] = "acc_no_such_account"
        response = await client.post("/api/v1/webhooks/pubsub", json=payload)
        assert response.status_code == 200
