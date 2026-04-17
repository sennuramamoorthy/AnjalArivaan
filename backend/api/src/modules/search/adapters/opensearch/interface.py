"""ISearchIndex — abstraction over a BM25 full-text store (OpenSearch).

D16: every operation is scoped to a single ``account_id``. Implementations
MUST physically map ``(account_id, doc_type)`` to a per-account index name
(e.g. ``mail-{account_id}``) and MUST NEVER query across accounts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ISearchIndex(ABC):
    @abstractmethod
    async def index_document(self, account_id: str, doc: dict[str, Any]) -> None:
        """Upsert ``doc`` into the per-account index for ``doc['type']``.

        ``doc`` must carry an ``id`` key. Supported ``type`` values:
        ``"mail"`` → ``mail-{account_id}``;
        ``"attachment"`` → ``attachments-{account_id}``.
        """

    @abstractmethod
    async def delete_document(
        self, account_id: str, doc_id: str, *, doc_type: str = "mail"
    ) -> None:
        """Remove a document from the per-account index."""

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        account_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """BM25 search over the per-account indices.

        ``filters['type']`` may be ``"mail"``, ``"attachment"``, or ``"all"``.
        Returns a list of ``{id, score, source}`` dicts — never crossing
        account boundaries.
        """
