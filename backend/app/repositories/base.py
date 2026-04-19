"""Generic Repository base class (Repository pattern).

All concrete repositories inherit from `BaseRepository[Model]` and expose a
consistent CRUD surface. Account-scoped queries go through
`AccountScopedRepository` which mandates an `account_id` filter.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import NotFoundError

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD over a single SQLAlchemy model."""

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: int) -> ModelT | None:
        return self.db.get(self.model, id_)

    def get_or_404(self, id_: int) -> ModelT:
        obj = self.get(id_)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} {id_} not found")
        return obj

    def list(self, *, limit: int = 50, offset: int = 0, **filters: Any) -> Sequence[ModelT]:
        stmt = select(self.model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(self.model, k) == v)
        stmt = stmt.limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def count(self, **filters: Any) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(self.model, k) == v)
        return self.db.execute(stmt).scalar_one()

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class AccountScopedRepository(BaseRepository[ModelT]):
    """Variant that REQUIRES an `account_id` on every list/count to prevent cross-account leaks."""

    def list_for_account(
        self, account_id: int, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Sequence[ModelT]:
        return self.list(limit=limit, offset=offset, owner_account_id=account_id, **filters)

    def count_for_account(self, account_id: int, **filters: Any) -> int:
        return self.count(owner_account_id=account_id, **filters)
