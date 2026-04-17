"""
Tests for AccountLinkService — TDD-first.

Uses InMemoryLinkedAccountRepo, MockGoogleOAuthAdapter, and MockAccountLinkVaultAdapter.
"""

import pytest

from src.modules.account_link.adapters.google_oauth.mock_adapter import MockGoogleOAuthAdapter
from src.modules.account_link.adapters.vault.mock_vault_adapter import MockAccountLinkVaultAdapter
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.account_link.services.account_link_service import AccountLinkService


class _FakeRedis:
    """Minimal Redis stand-in for tests — supports get/set/delete with TTL."""

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
def service(repo, google_oauth, redis, vault):
    return AccountLinkService(
        repo=repo,
        google_oauth=google_oauth,
        redis_client=redis,
        vault_adapter=vault,
    )


class TestInitiateOAuth:
    async def test_initiate_oauth_returns_auth_url_and_state(self, service):
        result = await service.initiate_oauth(
            user_id="user-1",
            redirect_uri="https://app.example.com/callback",
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        assert "authorization_url" in result
        assert "state" in result
        assert "accounts.google.com" in result["authorization_url"]
        assert len(result["state"]) == 32  # uuid4 hex

    async def test_initiate_stores_state_in_redis(self, service, redis):
        result = await service.initiate_oauth(
            user_id="user-1",
            redirect_uri="https://app.example.com/callback",
            scopes=[],
        )
        import json
        stored = json.loads(redis.get(f"oauth_state:{result['state']}"))
        assert stored["user_id"] == "user-1"
        assert stored["redirect_uri"] == "https://app.example.com/callback"


class TestCompleteOAuth:
    async def test_complete_oauth_creates_linked_account(
        self, service, redis, repo
    ):
        # Simulate initiate first
        result = await service.initiate_oauth(
            user_id="user-1",
            redirect_uri="https://app.example.com/callback",
            scopes=[],
        )
        state = result["state"]

        account = await service.complete_oauth(
            user_id="user-1", code="auth-code-123", state=state
        )
        assert account.app_user_id == "user-1"
        assert account.google_email == "user@takshashilauniv.ac.in"
        assert account.workspace_domain == "takshashilauniv.ac.in"
        assert account.status == "ACTIVE"
        assert account.vault_ref.startswith("vault:")

        # Should be persisted
        stored = await repo.find_by_id(account.id)
        assert stored is not None
        assert stored.google_email == account.google_email

    async def test_complete_oauth_rejects_invalid_state(self, service):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.complete_oauth(
                user_id="user-1", code="auth-code-123", state="bogus-state"
            )

    async def test_complete_oauth_rejects_wrong_user(self, service, redis):
        result = await service.initiate_oauth(
            user_id="user-1",
            redirect_uri="https://app.example.com/callback",
            scopes=[],
        )
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.complete_oauth(
                user_id="user-999", code="auth-code-123", state=result["state"]
            )

    async def test_complete_oauth_updates_existing_account(
        self, service, redis, repo
    ):
        # First link
        r1 = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account1 = await service.complete_oauth(
            user_id="user-1", code="code-1", state=r1["state"]
        )

        # Second link with same email should update (same id)
        r2 = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account2 = await service.complete_oauth(
            user_id="user-1", code="code-2", state=r2["state"]
        )

        assert account2.id == account1.id
        accounts = await repo.find_by_user("user-1")
        assert len(accounts) == 1


class TestGetLinkedAccounts:
    async def test_get_linked_accounts_returns_user_accounts(
        self, service, redis
    ):
        r = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        await service.complete_oauth(
            user_id="user-1", code="code-1", state=r["state"]
        )

        accounts = await service.get_linked_accounts("user-1")
        assert len(accounts) == 1
        assert accounts[0].app_user_id == "user-1"

    async def test_get_linked_accounts_empty_for_new_user(self, service):
        accounts = await service.get_linked_accounts("no-such-user")
        assert accounts == []


class TestRevokeAccount:
    async def test_revoke_sets_status_to_revoked(
        self, service, redis, repo, vault
    ):
        r = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account = await service.complete_oauth(
            user_id="user-1", code="code-1", state=r["state"]
        )

        await service.revoke_account(account_id=account.id, user_id="user-1")

        revoked = await repo.find_by_id(account.id)
        assert revoked.status == "REVOKED"
        assert len(vault.revoke_calls) == 1

    async def test_revoke_rejects_if_not_owned_by_user(
        self, service, redis, repo
    ):
        r = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account = await service.complete_oauth(
            user_id="user-1", code="code-1", state=r["state"]
        )

        with pytest.raises(PermissionError, match="not found or not owned"):
            await service.revoke_account(
                account_id=account.id, user_id="user-OTHER"
            )


class TestPermanentlyDeleteAccount:
    """Admins want the option to hard-delete a revoked linked account so
    the Settings list doesn't accumulate stale rows after repeated
    link/unlink cycles. Rules:

    - Only REVOKED accounts can be hard-deleted (enforces the two-step
      unlink → delete UX and prevents accidental loss of an active link).
    - Ownership is enforced (404 on someone else's account).
    - After delete the row is gone from the repo entirely.
    """

    async def _revoked_account(self, service, redis):
        r = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account = await service.complete_oauth(
            user_id="user-1", code="code-1", state=r["state"]
        )
        await service.revoke_account(account_id=account.id, user_id="user-1")
        return account

    async def test_delete_removes_revoked_account_from_repo(
        self, service, redis, repo
    ):
        account = await self._revoked_account(service, redis)

        await service.delete_account(account_id=account.id, user_id="user-1")

        assert await repo.find_by_id(account.id) is None

    async def test_delete_rejects_active_account(
        self, service, redis, repo
    ):
        r = await service.initiate_oauth(
            user_id="user-1", redirect_uri="http://x", scopes=[]
        )
        account = await service.complete_oauth(
            user_id="user-1", code="code-1", state=r["state"]
        )

        with pytest.raises(ValueError, match="must be revoked"):
            await service.delete_account(
                account_id=account.id, user_id="user-1"
            )

        # Row must still exist
        assert await repo.find_by_id(account.id) is not None

    async def test_delete_rejects_if_not_owned_by_user(
        self, service, redis, repo
    ):
        account = await self._revoked_account(service, redis)

        with pytest.raises(PermissionError, match="not found or not owned"):
            await service.delete_account(
                account_id=account.id, user_id="user-OTHER"
            )

        assert await repo.find_by_id(account.id) is not None

    async def test_delete_missing_account_raises(self, service):
        with pytest.raises(PermissionError):
            await service.delete_account(
                account_id="no-such-account", user_id="user-1"
            )
