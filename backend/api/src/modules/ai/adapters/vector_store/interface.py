"""Vector store adapter interface.

All access to Qdrant (or any vector store) goes through `IVectorStoreAdapter`.
Collection name MUST equal `account_id` (D16 strict per-account isolation);
adapters physically enforce this and raise `AccountIsolationError` on any
cross-account boundary violation.

The interface exposes two families of methods:

1. **Retrieval path** — used by `ContextAssembler` during AI request
   assembly. `search(collection, query_text, ...)` embeds the query text
   and returns ranked chunks from *only* `collection_name = collection`.

2. **Lifecycle path** — used by the account-link and mail-sync flows:
    * `ensure_collection(account_id)` — idempotent create on first link.
    * `upsert_chunks(account_id, chunks)` — bulk insert after a mail sync,
      with a physical D16 guard on every chunk.
    * `delete_account_data(account_id)` — drops the whole collection on
      account revoke.
"""

from abc import ABC, abstractmethod

from src.modules.ai.domain.embedding import ChunkEmbedding, SearchHit


class IVectorStoreAdapter(ABC):
    # ── Retrieval path (existing, used by ContextAssembler) ──────────────

    @abstractmethod
    async def search(
        self,
        collection: str,          # = account_id (namespace enforcement)
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        """
        Returns [{"chunk_id": str, "text": str, "score": float, "source_mail_id": str}]

        `collection` MUST equal the account_id whose context is being
        assembled. The adapter physically scopes the query to that
        collection only (D16).
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        """Low-level single-point upsert. Prefer `upsert_chunks` for new code."""
        ...

    # ── Lifecycle path (D16 per-account isolation) ───────────────────────

    @abstractmethod
    async def ensure_collection(self, account_id: str) -> None:
        """Idempotently create the per-account Qdrant collection.

        Collection name MUST equal `account_id` (D16). If the collection
        already exists, this is a no-op.
        """
        ...

    @abstractmethod
    async def upsert_chunks(
        self,
        account_id: str,
        chunks: list[ChunkEmbedding],
    ) -> int:
        """Upsert a batch of embedded chunks into `account_id`'s collection.

        For every chunk in `chunks`, `chunk.account_id` MUST equal
        `account_id`. If any chunk's `account_id` is different, the
        adapter raises `AccountIsolationError` and upserts nothing (D16
        physical guard — this is a crash-loud server bug).

        Returns the count of chunks upserted.
        """
        ...

    @abstractmethod
    async def delete_account_data(self, account_id: str) -> None:
        """Drop the entire collection for `account_id` (account revoke flow).

        Swallows 404 / missing-collection errors — this is idempotent.
        """
        ...
