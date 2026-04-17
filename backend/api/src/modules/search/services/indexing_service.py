"""SearchIndexingService — owned hook for the mail-sync and attachment
pipelines to feed documents into both the BM25 index and the vector store.

Every call carries ``account_id`` and the service guarantees D16 by
routing to per-account indices / collections only. Failures are logged
and swallowed: indexing is best-effort and MUST NOT fail mail-sync.
"""

from __future__ import annotations

from typing import Any

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.modules.search.adapters.embedding.interface import IEmbeddingAdapter
from src.modules.search.adapters.opensearch.interface import ISearchIndex


class SearchIndexingService:
    def __init__(
        self,
        *,
        search_index: ISearchIndex,
        vector_store: IVectorStoreAdapter | None,
        embedding_adapter: IEmbeddingAdapter | None,
        logger: Any,
    ) -> None:
        self._index = search_index
        self._vectors = vector_store
        self._embedder = embedding_adapter
        self._logger = logger

    async def index_message(self, account_id: str, message: Any) -> None:
        """Index a newly synced ``MailMessage`` into BM25 + vectors.

        ``message`` is duck-typed: anything exposing ``id``, ``subject``,
        ``body_text``, ``from_address``, ``received_at`` works.
        """
        log = self._logger.child(account_id=account_id, mail_id=getattr(message, "id", None))
        doc = {
            "id": getattr(message, "id", ""),
            "type": "mail",
            "subject": getattr(message, "subject", "") or "",
            "body": getattr(message, "body_text", "") or "",
            "from": getattr(message, "from_address", "") or "",
            "received_at": getattr(
                getattr(message, "received_at", None), "isoformat", lambda: ""
            )(),
        }
        try:
            await self._index.index_document(account_id, doc)
        except Exception as exc:  # noqa: BLE001
            log.warn("search.index_mail_failed", error=str(exc))

        if self._vectors is None or self._embedder is None:
            return
        try:
            body = (doc["subject"] + "\n\n" + doc["body"]).strip()
            if not body:
                return
            vector = await self._embedder.embed(body)
            chunk = ChunkEmbedding(
                chunk_id=f"{doc['id']}:0",
                account_id=account_id,
                mail_id=doc["id"],
                text=body[:4000],
                vector=vector,
                metadata={"source_mail_id": doc["id"], "type": "mail"},
            )
            await self._vectors.upsert_chunks(account_id, [chunk])
        except Exception as exc:  # noqa: BLE001
            log.warn("search.vector_upsert_failed", error=str(exc))

    async def index_attachment(
        self,
        account_id: str,
        attachment_id: str,
        ocr_text: str,
        *,
        filename: str = "",
        mail_id: str | None = None,
    ) -> None:
        """Clean hook for the attachment pipeline agent to feed OCR text.

        Writes a document into ``attachments-{account_id}`` and, if an
        embedder + vector store are configured, also upserts an embedding
        into the per-account Qdrant collection.
        """
        log = self._logger.child(
            account_id=account_id, attachment_id=attachment_id, mail_id=mail_id
        )
        doc = {
            "id": attachment_id,
            "type": "attachment",
            "filename": filename,
            "ocr_text": ocr_text or "",
            "mail_id": mail_id or "",
        }
        try:
            await self._index.index_document(account_id, doc)
        except Exception as exc:  # noqa: BLE001
            log.warn("search.index_attachment_failed", error=str(exc))

        if self._vectors is None or self._embedder is None:
            return
        if not (ocr_text or "").strip():
            return
        try:
            vector = await self._embedder.embed(ocr_text[:4000])
            chunk = ChunkEmbedding(
                chunk_id=f"att:{attachment_id}:0",
                account_id=account_id,
                mail_id=mail_id or "",
                text=ocr_text[:4000],
                vector=vector,
                metadata={
                    "attachment_id": attachment_id,
                    "type": "attachment",
                    "filename": filename,
                },
            )
            await self._vectors.upsert_chunks(account_id, [chunk])
        except Exception as exc:  # noqa: BLE001
            log.warn("search.vector_upsert_attachment_failed", error=str(exc))
