"""
Tests for Account Link REST API routes.

Uses TestClient with FakeAuthService, InMemoryLinkedAccountRepo,
MockGoogleOAuthAdapter, and MockAccountLinkVaultAdapter.
"""

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.adapters.google_oauth.mock_adapter import MockGoogleOAuthAdapter
from src.modules.account_link.adapters.vault.mock_vault_adapter import MockAccountLinkVaultAdapter
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.account_link.services.account_link_service import AccountLinkService


class _FakeAuthService:
    """Minimal auth service that always verifies tokens as a test user."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError

            raise TokenInvalidError("Invalid token")
        return {"sub": "user-1", "email": "test@example.com", "role": "dean"}


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def repo():
    return InMemoryLinkedAccountRepository()


@pytest.fixture
def google_oauth():
    return MockGoogleOAuthAdapter()


@pytest.fixture
def vault():
    return MockAccountLinkVaultAdapter()


@pytest.fixture
def redis():
    return _FakeRedis()


@pytest.fixture
def app(repo, google_oauth, redis, vault):
    application = create_app(auth_service=_FakeAuthService())
    service = AccountLinkService(
        repo=repo,
        google_oauth=google_oauth,
        redis_client=redis,
        vault_adapter=vault,
    )
    application.state.account_link_service = service
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class TestListLinkedAccounts:
    def test_list_linked_accounts_empty(self, client):
        resp = client.get("/api/v1/accounts/linked", headers=AUTH_HEADER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    def test_list_linked_accounts_returns_data(self, client):
        # Link an account first
        initiate_resp = client.post(
            "/api/v1/accounts/link/initiate",
            json={"redirectUri": "http://localhost/callback"},
            headers=AUTH_HEADER,
        )
        state = initiate_resp.json()["data"]["state"]

        client.get(
            "/api/v1/accounts/link/callback",
            params={"code": "auth-code", "state": state},
            headers=AUTH_HEADER,
        )

        resp = client.get("/api/v1/accounts/linked", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["googleEmail"] == "user@takshashilauniv.ac.in"
        assert data[0]["status"] == "ACTIVE"
        assert "id" in data[0]
        assert "workspaceDomain" in data[0]


class TestInitiateLink:
    def test_initiate_returns_auth_url(self, client):
        resp = client.post(
            "/api/v1/accounts/link/initiate",
            json={"redirectUri": "http://localhost/callback"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "authorizationUrl" in data
        assert "state" in data
        assert "accounts.google.com" in data["authorizationUrl"]


class TestOAuthCallback:
    def test_callback_creates_account(self, client):
        # Initiate first to get state
        init_resp = client.post(
            "/api/v1/accounts/link/initiate",
            json={"redirectUri": "http://localhost/callback"},
            headers=AUTH_HEADER,
        )
        state = init_resp.json()["data"]["state"]

        resp = client.get(
            "/api/v1/accounts/link/callback",
            params={"code": "auth-code", "state": state},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["googleEmail"] == "user@takshashilauniv.ac.in"
        assert data["status"] == "ACTIVE"

    def test_callback_rejects_invalid_state(self, client):
        resp = client.get(
            "/api/v1/accounts/link/callback",
            params={"code": "auth-code", "state": "bogus-state"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_STATE"


class TestRevokeAccount:
    def test_revoke_account(self, client):
        # Link first
        init_resp = client.post(
            "/api/v1/accounts/link/initiate",
            json={"redirectUri": "http://localhost/callback"},
            headers=AUTH_HEADER,
        )
        state = init_resp.json()["data"]["state"]
        cb_resp = client.get(
            "/api/v1/accounts/link/callback",
            params={"code": "auth-code", "state": state},
            headers=AUTH_HEADER,
        )
        account_id = cb_resp.json()["data"]["id"]

        resp = client.delete(
            f"/api/v1/accounts/linked/{account_id}",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True

        # Verify it's revoked
        list_resp = client.get("/api/v1/accounts/linked", headers=AUTH_HEADER)
        assert list_resp.json()["data"][0]["status"] == "REVOKED"


class TestAuthRequired:
    def test_routes_require_auth(self, client):
        # No auth header
        resp = client.get("/api/v1/accounts/linked")
        assert resp.status_code == 401

        resp = client.post(
            "/api/v1/accounts/link/initiate",
            json={"redirectUri": "http://localhost/callback"},
        )
        assert resp.status_code == 401

        resp = client.get(
            "/api/v1/accounts/link/callback",
            params={"code": "x", "state": "y"},
        )
        assert resp.status_code == 401

        resp = client.delete("/api/v1/accounts/linked/some-id")
        assert resp.status_code == 401

    def test_routes_reject_bad_token(self, client):
        bad_header = {"Authorization": "Bearer bad-token"}
        resp = client.get("/api/v1/accounts/linked", headers=bad_header)
        assert resp.status_code == 401
