"""Embedding domain model.

A `ChunkEmbedding` represents a single text chunk paired with its vector
embedding for storage in Qdrant. The `account_id` field is load-bearing:
D16 (strict per-account isolation) requires that every chunk carry the
account it belongs to, so the adapter can physically enforce that a
chunk is never upserted into a foreign collection.
"""

from dataclasses import dataclass, field


@dataclass
class ChunkEmbedding:
    """A single embedded text chunk ready for Qdrant upsert.

    Attributes:
        chunk_id: Stable unique identifier for the chunk (UUID or hash).
        account_id: The linked-account this chunk belongs to. MUST equal
            the Qdrant collection name when upserted (D16 isolation guard).
        mail_id: The source mail this chunk was extracted from.
        text: The raw chunk text (stored in Qdrant payload for retrieval).
        vector: The embedding vector (bge-m3 → 1024 dim).
        metadata: Arbitrary extra payload fields (e.g., `source_mail_id`,
            `chunk_index`, `received_at`).
    """

    chunk_id: str
    account_id: str
    mail_id: str
    text: str
    vector: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    """A single search result from the vector store."""

    chunk_id: str
    text: str
    score: float
    source_mail_id: str | None = None
    metadata: dict = field(default_factory=dict)
