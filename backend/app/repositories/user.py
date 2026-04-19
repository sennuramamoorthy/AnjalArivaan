"""User + LinkedAccount + RoleTemplate repositories."""
from sqlalchemy import select

from app.domain.models.user import AppUser, LinkedAccount, RoleTemplate
from app.repositories.base import BaseRepository


class AppUserRepository(BaseRepository[AppUser]):
    model = AppUser

    def get_by_email(self, email: str) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()


class LinkedAccountRepository(BaseRepository[LinkedAccount]):
    model = LinkedAccount

    def list_for_user(self, user_id: int) -> list[LinkedAccount]:
        stmt = select(LinkedAccount).where(LinkedAccount.app_user_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_google_email(self, email: str) -> LinkedAccount | None:
        stmt = select(LinkedAccount).where(LinkedAccount.google_email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()


class RoleTemplateRepository(BaseRepository[RoleTemplate]):
    model = RoleTemplate

    def get_by_designation(self, designation: str) -> RoleTemplate | None:
        stmt = select(RoleTemplate).where(RoleTemplate.designation == designation)
        return self.db.execute(stmt).scalar_one_or_none()
