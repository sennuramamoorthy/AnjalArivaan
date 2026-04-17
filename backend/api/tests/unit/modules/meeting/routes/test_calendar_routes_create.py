"""TDD: tests for POST /api/v1/calendar/events (event creation).

Mirrors the GET route's auth + D16 ownership posture. Accepts a JSON body
with ``accountId``, ``summary``, ``start``, ``end`` (ISO-8601) plus
optional ``description``, ``location``, ``attendees``.
"""

import asyncio
import logging
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.meeting.adapters.calendar.mock_adapter import MockCalendarAdapter


AUTH = {"Authorization": "Bearer tok"}


class _FakeAuthService:
    def verify_access_token(self, token: str):
        if token == "bad":
            from src.shared.domain.errors import TokenInvalidError

            raise TokenInvalidError("bad")
        return {"sub": "user-1", "email": "vc@t.ac.in", "role": "SUPER_ADMIN"}


def _seed_account(repo: InMemoryLinkedAccountRepository, *, id: str, user_id: str):
    acct = LinkedAccount(
        id=id,
        app_user_id=user_id,
        google_email=f"{user_id}@t.ac.in",
        workspace_domain="t.ac.in",
        scopes=["calendar.events"],
        vault_ref=f"vault:{id}",
        status="ACTIVE",
        last_sync_at=None,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    asyncio.run(repo.save(acct))


@pytest.fixture
def calendar_service() -> MockCalendarAdapter:
    return MockCalendarAdapter()


@pytest.fixture
def linked_repo() -> InMemoryLinkedAccountRepository:
    return InMemoryLinkedAccountRepository()


@pytest.fixture
def client(calendar_service, linked_repo) -> TestClient:
    app = create_app(auth_service=_FakeAuthService())
    app.state.calendar_service = calendar_service
    app.state.linked_account_repo = linked_repo
    return TestClient(app)


_VALID_BODY = {
    "accountId": "acc-1",
    "summary": "Governance Council",
    "start": "2026-04-20T10:00:00+00:00",
    "end": "2026-04-20T11:00:00+00:00",
    "description": "Monthly council meeting",
    "location": "Main Block",
    "attendees": [{"email": "dean@t.ac.in", "name": "Dean"}],
}


# ── Tests ──────────────────────────────────────────────────────────────────


def test_create_requires_auth(client):
    resp = client.post("/api/v1/calendar/events", json=_VALID_BODY)
    assert resp.status_code == 401


def test_create_foreign_account_returns_403(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-2")
    resp = client.post("/api/v1/calendar/events", json=_VALID_BODY, headers=AUTH)
    assert resp.status_code == 403


def test_create_unknown_account_returns_404(client, linked_repo):
    body = {**_VALID_BODY, "accountId": "no-such"}
    resp = client.post("/api/v1/calendar/events", json=body, headers=AUTH)
    assert resp.status_code == 404


def test_create_missing_summary_returns_400(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    body = {k: v for k, v in _VALID_BODY.items() if k != "summary"}
    resp = client.post("/api/v1/calendar/events", json=body, headers=AUTH)
    assert resp.status_code == 400


def test_create_missing_start_returns_400(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    body = {k: v for k, v in _VALID_BODY.items() if k != "start"}
    resp = client.post("/api/v1/calendar/events", json=body, headers=AUTH)
    assert resp.status_code == 400


def test_create_missing_end_returns_400(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    body = {k: v for k, v in _VALID_BODY.items() if k != "end"}
    resp = client.post("/api/v1/calendar/events", json=body, headers=AUTH)
    assert resp.status_code == 400


def test_create_valid_body_returns_200_with_event_id(
    client, linked_repo, calendar_service
):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    resp = client.post("/api/v1/calendar/events", json=_VALID_BODY, headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"]
    assert data["title"] == "Governance Council"
    assert data["location"] == "Main Block"


def test_create_event_then_appears_in_list(client, linked_repo, calendar_service):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    resp = client.post("/api/v1/calendar/events", json=_VALID_BODY, headers=AUTH)
    assert resp.status_code == 200
    created_id = resp.json()["data"]["id"]

    resp2 = client.get(
        "/api/v1/calendar/events?accountId=acc-1&from=2026-04-20&to=2026-04-20",
        headers=AUTH,
    )
    assert resp2.status_code == 200
    ids = {e["id"] for e in resp2.json()["data"]}
    assert created_id in ids


def test_create_logs_duration_ms(client, linked_repo, caplog):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")

    class _CapLogger:
        def __init__(self):
            self.calls = []

        def info(self, event, **kw):
            self.calls.append((event, kw))

        def warn(self, *a, **kw):
            pass

        def error(self, *a, **kw):
            pass

    cap = _CapLogger()
    client.app.state.logger = cap

    resp = client.post("/api/v1/calendar/events", json=_VALID_BODY, headers=AUTH)
    assert resp.status_code == 200, resp.text

    create_logs = [c for c in cap.calls if c[0] == "calendar.create"]
    assert create_logs, f"expected calendar.create log, got {cap.calls}"
    _, kw = create_logs[0]
    assert "duration_ms" in kw
    assert isinstance(kw["duration_ms"], (int, float))
