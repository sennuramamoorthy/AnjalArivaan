"""LinkedAccount domain model — represents a user's linked Google Workspace account."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LinkedAccount:
    id: str
    app_user_id: str
    google_email: str
    workspace_domain: str
    scopes: list[str]
    vault_ref: str
    status: str  # ACTIVE, REVOKED, SYNC_ERROR
    last_sync_at: datetime | None
    created_at: datetime
