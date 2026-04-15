"""
TDD - tests for MailSyncService.

Run BEFORE implementing src/modules/mail/services/sync_service.py.
All tests should initially FAIL.
"""

import pytest
import base64

from src.modules.mail.services.sync_service import MailSyncService
from src.modules.mail.adapters.gmail.mock_gmail_adapter import MockGmailAdapter
from src.modules.mail.adapters.vault.mock_vault_adapter import MockVaultAdapter
from src.modules.mail.adapters.storage.mock_storage_adapter import MockObjectStorage
from src.modules.mail.adapters.messaging.mock_message_bus import MockMessageBus
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.domain.events import NewMailEvent, AttachmentReadyEvent
from src.infra.logger import create_logger


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_MESSAGE_SIMPLE = {
    "id": "gm_001",
    "threadId": "thread_001",
    "labelIds": ["INBOX", "UNREAD"],
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "gov@ugc.gov.in"},
            {"name": "To", "value": "vc@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "Test Subject"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 09:00:00 +0530"},
        ],
        "body": {"data": _b64("Test body content.")},
        "parts": [],
    },
    "sizeEstimate": 512,
    "internalDate": "1744428000000",
}

FAKE_MESSAGE_WITH_ATTACHMENT = {
    "id": "gm_002",
    "threadId": "thread_002",
    "labelIds": ["INBOX"],
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [
            {"name": "From", "value": "sender@aicte-india.org"},
            {"name": "To", "value": "vc@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "With Attachment"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 10:00:00 +0530"},
        ],
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": _b64("See attached.")},
            },
            {
                "mimeType": "application/pdf",
                "filename": "report.pdf",
                "body": {
                    "attachmentId": "att_gm_002",
                    "size": 1024,
                },
            },
        ],
    },
    "sizeEstimate": 2048,
    "internalDate": "1744431600000",
}


@pytest.fixture
def gmail_adapter() -> MockGmailAdapter:
    return MockGmailAdapter(messages=[FAKE_MESSAGE_SIMPLE])


@pytest.fixture
def vault_adapter() -> MockVaultAdapter:
    return MockVaultAdapter(tokens={"acc_001": "fake_access_token"})


@pytest.fixture
def mail_repo() -> InMemoryMailRepository:
    return InMemoryMailRepository()


@pytest.fixture
def object_storage() -> MockObjectStorage:
    return MockObjectStorage()


@pytest.fixture
def message_bus() -> MockMessageBus:
    return MockMessageBus()


@pytest.fixture
def sync_service(
    gmail_adapter: MockGmailAdapter,
    vault_adapter: MockVaultAdapter,
    mail_repo: InMemoryMailRepository,
    object_storage: MockObjectStorage,
    message_bus: MockMessageBus,
) -> MailSyncService:
    logger = create_logger("mail-sync-test", trace_id="trace_test_001")
    return MailSyncService(
        gmail_adapter=gmail_adapter,
        vault_adapter=vault_adapter,
        mail_repo=mail_repo,
        object_storage=object_storage,
        message_bus=message_bus,
        logger=logger,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMailSyncService:

    async def test_sync_new_message_stores_in_repository(
        self,
        sync_service: MailSyncService,
        mail_repo: InMemoryMailRepository,
    ) -> None:
        count = await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_001",
        )
        assert count == 1
        stored = await mail_repo.find_by_gmail_msg_id("gm_001", "acc_001")
        assert stored is not None
        assert stored.gmail_msg_id == "gm_001"
        assert stored.account_id == "acc_001"

    async def test_sync_publishes_new_mail_event_to_kafka(
        self,
        sync_service: MailSyncService,
        message_bus: MockMessageBus,
    ) -> None:
        await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_001",
        )
        events = message_bus.get_published("mail-events")
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "mail.new"
        assert event["account_id"] == "acc_001"
        assert event["gmail_msg_id"] == "gm_001"

    async def test_sync_uploads_attachment_to_object_storage(
        self,
        vault_adapter: MockVaultAdapter,
        mail_repo: InMemoryMailRepository,
        object_storage: MockObjectStorage,
        message_bus: MockMessageBus,
    ) -> None:
        logger = create_logger("mail-sync-test")
        # Use an adapter with the attachment message
        gmail_with_attachment = MockGmailAdapter(messages=[FAKE_MESSAGE_WITH_ATTACHMENT])
        vault_adapter.tokens["acc_002"] = "fake_token_002"
        # Provide attachment bytes when fetched
        gmail_with_attachment.attachment_data[("gm_002", "att_gm_002")] = b"%PDF-fake-bytes"

        service = MailSyncService(
            gmail_adapter=gmail_with_attachment,
            vault_adapter=vault_adapter,
            mail_repo=mail_repo,
            object_storage=object_storage,
            message_bus=message_bus,
            logger=logger,
        )
        await service.sync_account(
            account_id="acc_002",
            user_id="user_002",
            trace_id="trace_002",
        )
        uploads = object_storage.get_uploads()
        assert len(uploads) == 1
        bucket, key, data, content_type = uploads[0]
        assert bucket == "attachments"
        assert "gm_002" in key or "report.pdf" in key
        assert data == b"%PDF-fake-bytes"

    async def test_sync_publishes_attachment_ready_event(
        self,
        vault_adapter: MockVaultAdapter,
        mail_repo: InMemoryMailRepository,
        object_storage: MockObjectStorage,
        message_bus: MockMessageBus,
    ) -> None:
        logger = create_logger("mail-sync-test")
        gmail_with_attachment = MockGmailAdapter(messages=[FAKE_MESSAGE_WITH_ATTACHMENT])
        vault_adapter.tokens["acc_002"] = "fake_token_002"
        gmail_with_attachment.attachment_data[("gm_002", "att_gm_002")] = b"%PDF-fake-bytes"

        service = MailSyncService(
            gmail_adapter=gmail_with_attachment,
            vault_adapter=vault_adapter,
            mail_repo=mail_repo,
            object_storage=object_storage,
            message_bus=message_bus,
            logger=logger,
        )
        await service.sync_account(
            account_id="acc_002",
            user_id="user_002",
            trace_id="trace_002",
        )
        att_events = message_bus.get_published("attachment-events")
        assert len(att_events) == 1
        att_event = att_events[0]
        assert att_event["event_type"] == "attachment.ready"
        assert att_event["account_id"] == "acc_002"

    async def test_sync_skips_already_synced_message(
        self,
        sync_service: MailSyncService,
        mail_repo: InMemoryMailRepository,
        message_bus: MockMessageBus,
    ) -> None:
        # First sync
        await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_001",
        )
        count_first = len(message_bus.get_published("mail-events"))

        # Second sync — same message already in repo, should be skipped
        await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_001",
        )
        count_second = len(message_bus.get_published("mail-events"))
        assert count_second == count_first  # no new events published

    async def test_sync_handles_empty_message_list(
        self,
        vault_adapter: MockVaultAdapter,
        mail_repo: InMemoryMailRepository,
        object_storage: MockObjectStorage,
        message_bus: MockMessageBus,
    ) -> None:
        logger = create_logger("mail-sync-test")
        empty_gmail = MockGmailAdapter(messages=[])
        vault_adapter.tokens["acc_003"] = "fake_token_003"

        service = MailSyncService(
            gmail_adapter=empty_gmail,
            vault_adapter=vault_adapter,
            mail_repo=mail_repo,
            object_storage=object_storage,
            message_bus=message_bus,
            logger=logger,
        )
        count = await service.sync_account(
            account_id="acc_003",
            user_id="user_003",
            trace_id="trace_003",
        )
        assert count == 0
        assert message_bus.get_published("mail-events") == []

    async def test_sync_uses_account_scoped_gmail_credentials(
        self,
        sync_service: MailSyncService,
        vault_adapter: MockVaultAdapter,
    ) -> None:
        await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_001",
        )
        # Vault adapter must have been called with the correct account_id
        assert "acc_001" in vault_adapter.called_with_account_ids

    async def test_new_mail_event_contains_correct_fields(
        self,
        sync_service: MailSyncService,
        message_bus: MockMessageBus,
    ) -> None:
        await sync_service.sync_account(
            account_id="acc_001",
            user_id="user_001",
            trace_id="trace_event_fields",
        )
        events = message_bus.get_published("mail-events")
        assert len(events) == 1
        event = events[0]

        required_fields = [
            "event_id", "event_type", "account_id", "user_id",
            "trace_id", "occurred_at", "mail_id", "gmail_msg_id",
            "thread_id", "from_address", "subject", "received_at",
            "has_attachment",
        ]
        for field in required_fields:
            assert field in event, f"Missing field: {field}"

        assert event["event_type"] == "mail.new"
        assert event["account_id"] == "acc_001"
        assert event["user_id"] == "user_001"
        assert event["gmail_msg_id"] == "gm_001"
        assert event["has_attachment"] is False
