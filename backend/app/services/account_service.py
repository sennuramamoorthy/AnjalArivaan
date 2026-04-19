"""Linked-account management: OAuth linking, switching, isolation (PRD §3.1, §4.2)."""
from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlencode

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ConflictError, ValidationError
from app.domain.models.user import AccountStatus, LinkedAccount
from app.integrations.vault.base import SecretStore
from app.repositories.user import LinkedAccountRepository


class AccountService:
    """Owns the OAuth dance and the per-account isolation invariant."""

    def __init__(self, accounts: LinkedAccountRepository, secrets: SecretStore) -> None:
        self.accounts = accounts
        self.secrets = secrets

    # ---- OAuth start/callback ---------------------------------------------

    def start_oauth(self, user_id: int) -> tuple[str, str]:
        """Return (authorization_url, state)."""
        state = token_urlsafe(32)
        # State is echoed back by Google; the caller must verify it.
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(
                [
                    "https://www.googleapis.com/auth/gmail.modify",
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/contacts.readonly",
                    "https://www.googleapis.com/auth/gmail.settings.basic",
                    "https://www.googleapis.com/auth/drive.file",
                    "openid",
                    "email",
                    "profile",
                ]
            ),
            "access_type": "offline",
            "prompt": "consent",
            "hd": settings.GOOGLE_WORKSPACE_ALLOWED_DOMAIN,
            "state": f"{user_id}:{state}",
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
        return url, state

    def complete_oauth(
        self,
        user_id: int,
        google_email: str,
        workspace_domain: str,
        refresh_token: str,
        scopes: list[str],
    ) -> LinkedAccount:
        if workspace_domain != settings.GOOGLE_WORKSPACE_ALLOWED_DOMAIN:
            raise ValidationError(
                f"Workspace '{workspace_domain}' is not whitelisted — must be "
                f"{settings.GOOGLE_WORKSPACE_ALLOWED_DOMAIN}"
            )
        if self.accounts.get_by_google_email(google_email):
            raise ConflictError(f"Account {google_email} is already linked")
        vault_ref = f"oauth/{user_id}/{google_email}"
        self.secrets.write(
            vault_ref,
            {"refresh_token": refresh_token, "scopes": scopes, "google_email": google_email},
        )
        acct = LinkedAccount(
            app_user_id=user_id,
            google_email=google_email.lower(),
            workspace_domain=workspace_domain,
            scopes=scopes,
            vault_ref=vault_ref,
            status=AccountStatus.ACTIVE,
        )
        self.accounts.add(acct)
        self.accounts.commit()
        return acct

    # ---- Switching / isolation --------------------------------------------

    def ensure_ownership(self, user_id: int, account_id: int) -> LinkedAccount:
        """Guard clause — used by all account-scoped routes to prevent IDOR."""
        acct = self.accounts.get_or_404(account_id)
        if acct.app_user_id != user_id:
            raise AuthorizationError("You do not own this linked account")
        return acct

    def list_for_user(self, user_id: int) -> list[LinkedAccount]:
        return self.accounts.list_for_user(user_id)
