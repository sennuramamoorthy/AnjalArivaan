"""Contacts, signature, OOO services (PRD §3.10)."""
from __future__ import annotations

from datetime import datetime

from app.domain.models.contact import Contact, OutOfOffice, SignatureTemplate
from app.domain.schemas.contact import (
    ContactCreate,
    OutOfOfficeCreate,
    SignatureCreate,
)
from app.integrations.google.base import GoogleMailClient
from app.repositories.contact import (
    ContactRepository,
    OutOfOfficeRepository,
    SignatureRepository,
)


class ContactsService:
    def __init__(self, repo: ContactRepository) -> None:
        self.repo = repo

    def create(self, account_id: int, payload: ContactCreate) -> Contact:
        c = Contact(owner_account_id=account_id, **payload.model_dump())
        self.repo.add(c)
        self.repo.commit()
        return c

    def list(self, account_id: int, limit: int = 50, offset: int = 0) -> list[Contact]:
        return list(
            self.repo.list_for_account(account_id, limit=limit, offset=offset)
        )


class SignatureService:
    def __init__(self, repo: SignatureRepository, google_mail: GoogleMailClient) -> None:
        self.repo = repo
        self.google_mail = google_mail

    def create(self, account_id: int, payload: SignatureCreate) -> SignatureTemplate:
        s = SignatureTemplate(owner_account_id=account_id, **payload.model_dump())
        self.repo.add(s)
        self.repo.commit()
        return s

    async def set_default(self, account_id: int, signature_id: int) -> SignatureTemplate:
        sig = self.repo.get_or_404(signature_id)
        if sig.owner_account_id != account_id:
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError("signature does not belong to this account")
        # clear previous default
        for existing in self.repo.list_for_account(account_id, limit=100):
            existing.is_default = existing.id == signature_id
        self.repo.commit()
        await self.google_mail.update_signature(account_id, sig.html)
        return sig


class OutOfOfficeService:
    def __init__(self, repo: OutOfOfficeRepository, google_mail: GoogleMailClient) -> None:
        self.repo = repo
        self.google_mail = google_mail

    async def set_ooo(
        self, account_id: int, payload: OutOfOfficeCreate
    ) -> OutOfOffice:
        # deactivate prior OOO
        existing = self.repo.active_for_account(account_id)
        if existing:
            existing.active = False
        ooo = OutOfOffice(owner_account_id=account_id, active=True, **payload.model_dump())
        self.repo.add(ooo)
        self.repo.commit()
        await self.google_mail.set_vacation(
            account_id, payload.message, payload.starts_at, payload.ends_at
        )
        return ooo

    def clear(self, account_id: int) -> None:
        existing = self.repo.active_for_account(account_id)
        if existing:
            existing.active = False
            existing.ends_at = datetime.utcnow()
            self.repo.commit()
