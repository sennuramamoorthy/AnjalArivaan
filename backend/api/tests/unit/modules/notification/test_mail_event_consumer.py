"""
Unit tests for MailEventHandler.process_message().
Tests are written FIRST (TDD).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.modules.notification.consumer.mail_event_handler import MailEventHandler


@pytest.fixture
def mock_notification_service():
    svc = AsyncMock()
    svc.process_new_mail = AsyncMock(return_value=MagicMock(is_urgent=False))
    return svc


@pytest.fixture
def handler(mock_notification_service):
    return MailEventHandler(
        notification_service=mock_notification_service,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processes_new_mail_event_calls_notification_service(handler, mock_notification_service):
    """A mail.new event should invoke notification_service.process_new_mail"""
    event = {
        "event_type": "mail.new",
        "account_id": "acct-001",
        "user_id": "user-vc-001",
        "trace_id": "trace-abc",
        "mail": {
            "id": "mail-001",
            "from_address": "secretary@ugc.gov.in",
            "subject": "Deadline Notice",
            "body_text": "Submit by 15 April 2026.",
            "labels": ["INBOX"],
        },
    }
    await handler.process_message(event)

    mock_notification_service.process_new_mail.assert_awaited_once()
    call_kwargs = mock_notification_service.process_new_mail.call_args
    assert call_kwargs.kwargs["mail"]["id"] == "mail-001"
    assert call_kwargs.kwargs["account_id"] == "acct-001"
    assert call_kwargs.kwargs["user_id"] == "user-vc-001"
    assert call_kwargs.kwargs["trace_id"] == "trace-abc"


@pytest.mark.asyncio
async def test_ignores_unknown_event_types(handler, mock_notification_service):
    """Events with unrecognised event_type must not invoke notification_service"""
    event = {
        "event_type": "mail.read",
        "account_id": "acct-001",
        "user_id": "user-vc-001",
        "trace_id": "trace-abc",
        "mail": {"id": "mail-002"},
    }
    await handler.process_message(event)
    mock_notification_service.process_new_mail.assert_not_called()


@pytest.mark.asyncio
async def test_handles_malformed_event_gracefully(handler, mock_notification_service):
    """A malformed / missing-key event must not raise an exception"""
    malformed = {"event_type": "mail.new"}  # missing 'mail', 'account_id', etc.
    # Should not raise
    await handler.process_message(malformed)
    # Service should not be called on a malformed event
    mock_notification_service.process_new_mail.assert_not_called()


@pytest.mark.asyncio
async def test_extracts_trace_id_from_event(handler, mock_notification_service):
    """trace_id must be forwarded from the event to notification_service"""
    event = {
        "event_type": "mail.new",
        "account_id": "acct-001",
        "user_id": "user-vc-001",
        "trace_id": "specific-trace-xyz-999",
        "mail": {
            "id": "mail-003",
            "from_address": "officer@mhrd.gov.in",
            "subject": "Inspection",
            "body_text": "Inspection scheduled.",
            "labels": ["INBOX"],
        },
    }
    await handler.process_message(event)

    call_kwargs = mock_notification_service.process_new_mail.call_args
    assert call_kwargs.kwargs["trace_id"] == "specific-trace-xyz-999"
