"""TDD: GET /api/v1/briefing/daily wired to the BriefingGeneratorService.

Covers:
  1. 200 with ``briefing`` + ``generatedAt`` + ``briefingDate`` in data
     envelope when the service is wired.
  2. 401 on missing auth; 400 on missing accountId; 404 on D16 violation
     (account belongs to a different user).
  3. Lazy backfill — service's get_or_generate is invoked and a new row
     lands in the repo after the call.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.in_memory_briefing_repo import (
    InMemoryBriefingRepository,
)
from src.modules.briefing.services.briefing_generator_service import (
    BriefingGeneratorService,
)


AUTH = {"Authorization": "Bearer valid-token"}


class _FakeAuth:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "vc@t.ac.in", "role": "vc"}


class _FakeLlm:
    def __init__(self, canned: str = "Briefing body text") -> None:
        self.canned = canned

    async def complete(self, prompt: str, **kw) -> str:
        return self.canned


@dataclass
class _FakeLinkedAccount:
    id: str
    app_user_id: str


class _FakeLinkedAccountRepo:
    def __init__(self, accounts: list[_FakeLinkedAccount]) -> None:
        self._accounts = {a.id: a for a in accounts}

    async def find_by_id(self, id: str) -> Optional[_FakeLinkedAccount]:
        return self._accounts.get(id)


def _build_app(
    *,
    briefing_repo=None,
    llm=None,
    linked_account_repo=None,
):
    app = create_app(auth_service=_FakeAuth())
    repo = briefing_repo or InMemoryBriefingRepository()
    svc = BriefingGeneratorService(
        briefing_repo=repo,
        llm_adapter=llm or _FakeLlm(),
        model_id="llama",
    )
    app.state.briefing_service = svc
    app.state.briefing_repo = repo
    if linked_account_repo is not None:
        app.state.linked_account_repo = linked_account_repo
    return app


# ───────────────────────── Tests ─────────────────────────


def test_returns_briefing_envelope():
    repo = InMemoryBriefingRepository()
    app = _build_app(briefing_repo=repo, llm=_FakeLlm("Hello"))
    client = TestClient(app)

    resp = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-1"}, headers=AUTH
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["briefing"] == "Hello"
    assert "generatedAt" in data
    assert "briefingDate" in data


def test_lazy_backfill_persists_row():
    repo = InMemoryBriefingRepository()
    app = _build_app(briefing_repo=repo, llm=_FakeLlm("Fresh"))
    client = TestClient(app)

    today = datetime.now(timezone.utc).date()
    assert asyncio.run(
        repo.find_for_day(user_id="user-1", account_id="a-1", briefing_date=today)
    ) is None

    resp = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-1"}, headers=AUTH
    )
    assert resp.status_code == 200

    stored = asyncio.run(
        repo.find_for_day(user_id="user-1", account_id="a-1", briefing_date=today)
    )
    assert stored is not None
    assert stored.body == "Fresh"


def test_401_when_missing_auth():
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/api/v1/briefing/daily", params={"accountId": "a-1"})
    assert resp.status_code == 401


def test_400_when_missing_account_id():
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/api/v1/briefing/daily", headers=AUTH)
    assert resp.status_code == 400


def test_404_when_account_does_not_belong_to_user():
    """D16: an account owned by a different user must 404, not leak."""
    linked = _FakeLinkedAccountRepo(
        [_FakeLinkedAccount(id="a-other", app_user_id="different-user")]
    )
    app = _build_app(linked_account_repo=linked)
    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-other"}, headers=AUTH
    )
    assert resp.status_code == 404


def test_200_when_account_belongs_to_user():
    linked = _FakeLinkedAccountRepo(
        [_FakeLinkedAccount(id="a-mine", app_user_id="user-1")]
    )
    app = _build_app(linked_account_repo=linked)
    client = TestClient(app)
    resp = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-mine"}, headers=AUTH
    )
    assert resp.status_code == 200


def test_returns_cached_briefing_on_second_call():
    repo = InMemoryBriefingRepository()
    llm = _FakeLlm("Once")
    app = _build_app(briefing_repo=repo, llm=llm)
    client = TestClient(app)

    r1 = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-1"}, headers=AUTH
    )
    assert r1.status_code == 200
    # Flip the LLM canned response; a cached response must still return "Once".
    llm.canned = "Twice"
    r2 = client.get(
        "/api/v1/briefing/daily", params={"accountId": "a-1"}, headers=AUTH
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["briefing"] == "Once"
