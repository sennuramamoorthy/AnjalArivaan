"""Mail, attachments, urgency rules (PRD §3.2, §3.3, §5)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MailMessage(Base):
    """Normalized mail record — Gmail remains the system of record (PRD §1.2, §3.2)."""

    __tablename__ = "mail_message"
    __table_args__ = (
        Index("ix_mail_account_received", "owner_account_id", "received_at"),
        Index("ix_mail_thread", "thread_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    gmail_msg_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    to_addresses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cc_addresses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    subject: Mapped[str] = mapped_column(String(998), default="", nullable=False)
    snippet: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    has_attachment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    urgency_score: Mapped[float] = mapped_column(default=0.0, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )


class AttachmentStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    QUARANTINED = "quarantined"
    INDEXED = "indexed"


class Attachment(Base):
    """File attachment with OCR/transcription pipeline state (PRD §3.13)."""

    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mail_id: Mapped[int] = mapped_column(ForeignKey("mail_message.id"), nullable=False, index=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minio_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ocr_lang: Mapped[str | None] = mapped_column(String(16))  # "tam+eng"
    av_transcript: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[AttachmentStatus] = mapped_column(
        String(16), default=AttachmentStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    mail: Mapped[MailMessage] = relationship(back_populates="attachments")


class UrgencyRule(Base):
    """Admin-configurable rule per role (PRD §3.3).

    Example payload:
      sender_patterns: ["*.gov.in", "*.nic.in", "ugc.gov.in"]
      keyword_patterns: ["URGENT", "Compliance", "Deadline"]
      deadline_regex: r"(?P<date>\\d{2}[-/]\\d{2}[-/]\\d{4})"
      action_template: "urgent_gov_whatsapp_v1"
    """

    __tablename__ = "urgency_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_designation: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_patterns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keyword_patterns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    deadline_regex: Mapped[str | None] = mapped_column(String(512))
    action_template: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
