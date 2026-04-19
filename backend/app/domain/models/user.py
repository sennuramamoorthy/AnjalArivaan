"""User, LinkedAccount, Role, RoleTemplate (PRD §3.1, §5)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDED = "offboarded"


class AppUser(Base):
    """A single app identity (PRD §3.1) — email + password + MFA.

    One AppUser may link multiple Google Workspace accounts via LinkedAccount.
    """

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(32))  # WhatsApp
    full_name: Mapped[str | None] = mapped_column(String(255))
    designation: Mapped[str | None] = mapped_column(String(128))  # e.g. "Vice Chancellor"
    department: Mapped[str | None] = mapped_column(String(128))
    reporting_to_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_dept_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[UserStatus] = mapped_column(String(16), default=UserStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    reporting_to: Mapped["AppUser"] = relationship(
        "AppUser", remote_side="AppUser.id", foreign_keys=[reporting_to_id]
    )
    linked_accounts: Mapped[list["LinkedAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AccountStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class LinkedAccount(Base):
    """A Google Workspace account linked via OAuth to an AppUser (PRD §3.1, §4.2).

    Refresh tokens are NEVER stored here — only a `vault_ref` pointing to the
    HashiCorp Vault secret path.
    """

    __tablename__ = "linked_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    google_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workspace_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    vault_ref: Mapped[str] = mapped_column(String(512), nullable=False)  # e.g. "secret/oauth/123"
    status: Mapped[AccountStatus] = mapped_column(
        String(16), default=AccountStatus.ACTIVE, nullable=False
    )
    gmail_history_id: Mapped[str | None] = mapped_column(String(64))  # for push reconciliation
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped[AppUser] = relationship(back_populates="linked_accounts")


class RoleTemplate(Base):
    """Role-specific persona + rules (PRD §2, §6.3)."""

    __tablename__ = "role_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    designation: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    persona_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    kpis: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    briefing_hour_ist: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    briefing_channel: Mapped[str] = mapped_column(String(16), default="app", nullable=False)
    urgency_rule_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
