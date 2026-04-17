"""AccountLinkService — orchestrates the Google OAuth account linking flow.

Design pattern: **Facade** — presents a single high-level API over the Google
OAuth adapter, Vault token broker, and linked-account repository.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from src.modules.account_link.adapters.google_oauth.interface import IGoogleOAuthAdapter
from src.modules.account_link.adapters.vault.interface import IAccountLinkVaultAdapter
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.interface import ILinkedAccountRepository

OAUTH_STATE_TTL = 600  # seconds


class AccountLinkService:
    def __init__(
        self,
        repo: ILinkedAccountRepository,
        google_oauth: IGoogleOAuthAdapter,
        redis_client,
        vault_adapter: IAccountLinkVaultAdapter,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repo
        self._google_oauth = google_oauth
        self._redis = redis_client
        self._vault = vault_adapter
        self._logger = logger or logging.getLogger(__name__)

    async def initiate_oauth(
        self, user_id: str, redirect_uri: str, scopes: list[str]
    ) -> dict:
        """
        Start the OAuth flow: generate a state token, store it in Redis,
        and return the Google authorization URL.

        Returns: {authorization_url, state}
        """
        state = uuid.uuid4().hex
        state_data = json.dumps({"user_id": user_id, "redirect_uri": redirect_uri})
        self._redis.set(
            f"oauth_state:{state}", state_data, ex=OAUTH_STATE_TTL
        )

        authorization_url = await self._google_oauth.build_auth_url(
            redirect_uri=redirect_uri,
            state=state,
            scopes=scopes,
        )

        self._logger.info(
            "OAuth flow initiated", user_id=user_id, state=state
        )
        return {"authorization_url": authorization_url, "state": state}

    async def complete_oauth(
        self, user_id: str, code: str, state: str
    ) -> LinkedAccount:
        """
        Complete the OAuth flow: verify state, exchange code for tokens,
        fetch user info, store refresh token in Vault, and persist the
        linked account.
        """
        raw = self._redis.get(f"oauth_state:{state}")
        if raw is None:
            raise ValueError("Invalid or expired OAuth state token")

        state_data = json.loads(raw)
        if state_data.get("user_id") != user_id:
            raise ValueError("Invalid or expired OAuth state token")

        redirect_uri = state_data.get("redirect_uri", "")
        self._redis.delete(f"oauth_state:{state}")

        tokens = await self._google_oauth.exchange_code(
            code=code, redirect_uri=redirect_uri
        )
        user_info = await self._google_oauth.get_user_info(
            access_token=tokens["access_token"]
        )

        google_email = user_info["email"]
        workspace_domain = google_email.split("@")[1] if "@" in google_email else ""

        # Check for existing linked account with same email for this user
        existing = await self._repo.find_by_email_and_user(google_email, user_id)

        account_id = existing.id if existing else uuid.uuid4().hex

        vault_ref = await self._vault.store_refresh_token(
            account_id=account_id,
            refresh_token=tokens["refresh_token"],
        )

        now = datetime.now(timezone.utc)
        account = LinkedAccount(
            id=account_id,
            app_user_id=user_id,
            google_email=google_email,
            workspace_domain=workspace_domain,
            scopes=[],  # populated from the OAuth flow scopes
            vault_ref=vault_ref,
            status="ACTIVE",
            last_sync_at=None,
            created_at=existing.created_at if existing else now,
        )

        saved = await self._repo.save(account)
        self._logger.info(
            "Linked account created", account_id=saved.id, user_id=user_id, email=google_email
        )
        return saved

    async def get_linked_accounts(
        self, user_id: str, *, include_revoked: bool = True
    ) -> list[LinkedAccount]:
        """Return linked accounts for a user.

        By default revoked accounts are **included** so the admin UI can
        show "disconnected" state and offer a reconnect action. Set
        ``include_revoked=False`` for flows that must only see accounts
        the user can currently act on (sync, send mail, etc.).
        """
        accounts = await self._repo.find_by_user(user_id)
        if include_revoked:
            return list(accounts)
        return [a for a in accounts if a.status != "REVOKED"]

    async def revoke_account(self, account_id: str, user_id: str) -> None:
        """
        Revoke a linked account: verify ownership, revoke Vault token,
        and set status to REVOKED.
        """
        account = await self._repo.find_by_id(account_id)
        if account is None or account.app_user_id != user_id:
            raise PermissionError("Account not found or not owned by user")

        await self._vault.revoke_refresh_token(account.vault_ref)
        await self._repo.update_status(account_id, "REVOKED")

        self._logger.info(
            "Linked account revoked", account_id=account_id, user_id=user_id
        )

    async def delete_account(self, account_id: str, user_id: str) -> None:
        """Hard-delete a revoked linked account.

        Two-step UX: the user first clicks "Unlink" (→ ``revoke_account``
        which cleans up Vault + flips status to REVOKED), then clicks
        "Delete" on the now-greyed-out row. We only allow hard-delete on
        REVOKED rows so an accidental click cannot nuke a working link,
        and so Vault cleanup always runs before the row disappears.

        Raises ``PermissionError`` when the account is missing or owned
        by someone else (collapsed to 404 at the edge to avoid leaking
        existence). Raises ``ValueError`` when the account is not in
        REVOKED state.
        """
        account = await self._repo.find_by_id(account_id)
        if account is None or account.app_user_id != user_id:
            raise PermissionError("Account not found or not owned by user")

        if account.status != "REVOKED":
            raise ValueError(
                "Account must be revoked before it can be permanently deleted"
            )

        await self._repo.delete_by_id(account_id)
        self._logger.info(
            "Linked account deleted",
            account_id=account_id,
            user_id=user_id,
        )
