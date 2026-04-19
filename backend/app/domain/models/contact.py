"""Contacts, signatures, out-of-office (PRD §3.10)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Contact(Base):
    """Per-account contact, synced from Gmail People API (PRD §3.10)."""

    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    emails: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    phones: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    org: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    google_resource_name: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SignatureTemplate(Base):
    """Gmail signature pushed via settings.basic scope (PRD §3.10)."""

    __tablename__ = "signature_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OutOfOffice(Base):
    """OOO with delegate routing (PRD §3.10)."""

    __tablename__ = "out_of_office"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delegate_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
