"""
TDD - tests for GmailMessageParser.

Run BEFORE implementing src/services/message_parser.py.
All tests should initially FAIL.
"""

import base64
import sys
import os

# Allow imports from src/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from services.message_parser import GmailMessageParser

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _b64(text: str) -> str:
    """URL-safe base64-encode a UTF-8 string (Gmail API format)."""
    return base64.urlsafe_b64encode(text.encode()).decode()


SIMPLE_RAW_MESSAGE = {
    "id": "msg_001",
    "threadId": "thread_001",
    "labelIds": ["INBOX", "UNREAD"],
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "ugc-secretary@ugc.gov.in"},
            {"name": "To", "value": "vc@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "Annual Report Submission Deadline"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 09:00:00 +0530"},
            {"name": "Message-ID", "value": "<abc123@ugc.gov.in>"},
            {"name": "Cc", "value": "registrar@takshashilauniv.ac.in"},
        ],
        "body": {
            "data": _b64("Please submit the annual report by April 15.")
        },
        "parts": [],
    },
    "sizeEstimate": 1024,
    "internalDate": "1744428000000",
}

ATTACHMENT_RAW_MESSAGE = {
    "id": "msg_002",
    "threadId": "thread_002",
    "labelIds": ["INBOX"],
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [
            {"name": "From", "value": "sender@aicte-india.org"},
            {"name": "To", "value": "vc@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "Accreditation Documents"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 10:00:00 +0530"},
        ],
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "text/plain",
                "headers": [{"name": "Content-Type", "value": "text/plain"}],
                "body": {"data": _b64("Please find attached the accreditation documents.")},
            },
            {
                "mimeType": "application/pdf",
                "headers": [
                    {"name": "Content-Type", "value": "application/pdf"},
                    {"name": "Content-Disposition", "value": 'attachment; filename="accreditation.pdf"'},
                ],
                "filename": "accreditation.pdf",
                "body": {
                    "attachmentId": "att_001",
                    "size": 204800,
                },
            },
        ],
    },
    "sizeEstimate": 205824,
    "internalDate": "1744431600000",
}

MULTIPART_ALTERNATIVE_MESSAGE = {
    "id": "msg_003",
    "threadId": "thread_003",
    "labelIds": ["INBOX"],
    "payload": {
        "mimeType": "multipart/alternative",
        "headers": [
            {"name": "From", "value": "noreply@nic.in"},
            {"name": "To", "value": "registrar@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "Portal Update Notification"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 08:00:00 +0530"},
        ],
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": _b64("Plain text version of the email.")},
            },
            {
                "mimeType": "text/html",
                "body": {"data": _b64("<html><body><p>HTML version of the email.</p></body></html>")},
            },
        ],
    },
    "sizeEstimate": 512,
    "internalDate": "1744424400000",
}

NO_BODY_MESSAGE = {
    "id": "msg_004",
    "threadId": "thread_004",
    "labelIds": ["INBOX"],
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "sender@ugc.gov.in"},
            {"name": "To", "value": "vc@takshashilauniv.ac.in"},
            {"name": "Subject", "value": "Empty Body Test"},
            {"name": "Date", "value": "Tue, 12 Apr 2026 07:00:00 +0530"},
        ],
        "body": {},
        "parts": [],
    },
    "sizeEstimate": 100,
    "internalDate": "1744420800000",
}


@pytest.fixture
def parser() -> GmailMessageParser:
    return GmailMessageParser()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGmailMessageParser:

    def test_parses_from_header(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert mail.from_address == "ugc-secretary@ugc.gov.in"

    def test_parses_to_header(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert "vc@takshashilauniv.ac.in" in mail.to_addresses

    def test_parses_subject_header(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert mail.subject == "Annual Report Submission Deadline"

    def test_parses_received_at_from_internal_date(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        # internalDate is epoch milliseconds: 1744428000000 ms → 1744428000 seconds
        assert mail.received_at.year == 2025
        assert mail.received_at.month == 4
        assert mail.received_at.day == 12

    def test_decodes_base64_body(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert mail.body_text == "Please submit the annual report by April 15."

    def test_detects_attachments(self, parser: GmailMessageParser) -> None:
        mail, attachments = parser.parse(ATTACHMENT_RAW_MESSAGE, account_id="acc_002")
        assert mail.has_attachment is True
        assert len(attachments) == 1
        assert attachments[0].filename == "accreditation.pdf"
        assert attachments[0].mime_type == "application/pdf"
        assert attachments[0].gmail_attachment_id == "att_001"

    def test_handles_multipart_mime(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(MULTIPART_ALTERNATIVE_MESSAGE, account_id="acc_003")
        assert mail.body_text == "Plain text version of the email."
        assert "<p>HTML version of the email.</p>" in mail.body_html

    def test_extracts_cc_header(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert "registrar@takshashilauniv.ac.in" in mail.cc_addresses

    def test_handles_missing_body(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(NO_BODY_MESSAGE, account_id="acc_001")
        assert mail.body_text == ""
        assert mail.body_html == ""

    def test_parses_labels(self, parser: GmailMessageParser) -> None:
        mail, _ = parser.parse(SIMPLE_RAW_MESSAGE, account_id="acc_001")
        assert "INBOX" in mail.labels
        assert "UNREAD" in mail.labels
