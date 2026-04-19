"""Common schemas (pagination, error envelope)."""
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
