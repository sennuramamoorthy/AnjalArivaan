"""Contact / signature / OOO repositories."""
from sqlalchemy import select

from app.domain.models.contact import Contact, OutOfOffice, SignatureTemplate
from app.repositories.base import AccountScopedRepository


class ContactRepository(AccountScopedRepository[Contact]):
    model = Contact


class SignatureRepository(AccountScopedRepository[SignatureTemplate]):
    model = SignatureTemplate

    def get_default(self, account_id: int) -> SignatureTemplate | None:
        stmt = (
            select(SignatureTemplate)
            .where(SignatureTemplate.owner_account_id == account_id)
            .where(SignatureTemplate.is_default.is_(True))
        )
        return self.db.execute(stmt).scalar_one_or_none()


class OutOfOfficeRepository(AccountScopedRepository[OutOfOffice]):
    model = OutOfOffice

    def active_for_account(self, account_id: int) -> OutOfOffice | None:
        stmt = (
            select(OutOfOffice)
            .where(OutOfOffice.owner_account_id == account_id)
            .where(OutOfOffice.active.is_(True))
        )
        return self.db.execute(stmt).scalars().first()
