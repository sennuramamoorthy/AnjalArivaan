"""User domain model and role enum."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    VC = "VC"
    REGISTRAR = "REGISTRAR"
    DEAN = "DEAN"
    HOD = "HOD"
    STAFF = "STAFF"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    phone: Optional[str] = None
    role: str = UserRole.STAFF
    status: str = UserStatus.ACTIVE
    name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    responsibilities: Optional[str] = None
    # In-memory only for Phase 1a — not persisted to DB yet.
    # Used by notification.MailEventHandler to decide who to forward urgent
    # government mail to. Resolved via user_repo at event time.
    line_manager_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PublicUser:
    """User data safe to return in API responses (no secrets)."""
    id: str
    email: str
    mfa_enabled: bool
    role: str
    status: str
    name: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    responsibilities: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
