"""TDD: tests for Calendar REST routes.

``GET /api/v1/calendar/events`` returns events for a linked account across
an optional date range. Auth is required; ownership is enforced via
``linked_account_repo`` (D16 — foreign accounts return 404, never 403).
"""

import asyncio
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.meeting.adapters.calendar.interface import CalendarEvent
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


def _make_event(**over) -> CalendarEvent:
    base = dict(
        id="evt-1",
        title="Governance Council",
        start=datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc),
        location="Main Block",
        attendees=["vc@t.ac.in"],
    )
    base.update(over)
    return CalendarEvent(**base)


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


# ── Tests ──────────────────────────────────────────────────────────────────


def test_list_requires_auth(client):
    resp = client.get("/api/v1/calendar/events?accountId=acc-1")
    assert resp.status_code == 401


def test_list_requires_account_id(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    resp = client.get("/api/v1/calendar/events", headers=AUTH)
    assert resp.status_code == 400


def test_foreign_account_returns_403(client, linked_repo):
    """D16 ownership: an account owned by another user is refused.

    Matches the shared ``require_account_ownership`` middleware used by
    send/mail/ai routes — 403 for known-but-foreign, 404 for not-exists.
    """
    _seed_account(linked_repo, id="other", user_id="user-2")
    resp = client.get("/api/v1/calendar/events?accountId=other", headers=AUTH)
    assert resp.status_code == 403


def test_unknown_account_returns_404(client, linked_repo):
    resp = client.get(
        "/api/v1/calendar/events?accountId=no-such-account", headers=AUTH
    )
    assert resp.status_code == 404


def test_list_events_for_today(client, linked_repo, calendar_service):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    calendar_service.set_default_events(
        account_id="acc-1",
        events=[_make_event(id="e1", title="Staff meeting")],
    )
    resp = client.get("/api/v1/calendar/events?accountId=acc-1", headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "e1"
    assert data[0]["title"] == "Staff meeting"
    assert data[0]["start"] == "2026-04-16T10:00:00+00:00"
    assert data[0]["end"] == "2026-04-16T11:00:00+00:00"
    assert data[0]["location"] == "Main Block"
    assert data[0]["attendees"] == ["vc@t.ac.in"]


def test_list_events_for_range(client, linked_repo, calendar_service):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    calendar_service.seed(
        account_id="acc-1",
        day=date(2026, 4, 16),
        events=[_make_event(id="d1-a")],
    )
    calendar_service.seed(
        account_id="acc-1",
        day=date(2026, 4, 17),
        events=[
            _make_event(
                id="d2-a",
                start=datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc),
                end=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )
    resp = client.get(
        "/api/v1/calendar/events?accountId=acc-1&from=2026-04-16&to=2026-04-17",
        headers=AUTH,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    ids = {e["id"] for e in data}
    assert ids == {"d1-a", "d2-a"}


def test_list_events_rejects_bad_date(client, linked_repo):
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    resp = client.get(
        "/api/v1/calendar/events?accountId=acc-1&from=nope", headers=AUTH
    )
    assert resp.status_code == 400


def test_service_unavailable_when_adapter_missing(linked_repo):
    app = create_app(auth_service=_FakeAuthService())
    app.state.linked_account_repo = linked_repo
    _seed_account(linked_repo, id="acc-1", user_id="user-1")
    # NOTE: no calendar_service on app.state
    resp = TestClient(app).get(
        "/api/v1/calendar/events?accountId=acc-1", headers=AUTH
    )
    assert resp.status_code == 503
