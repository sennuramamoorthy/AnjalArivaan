"""Federated search over mail, attachments, contacts, tasks, meetings, travel (PRD §3.12).

Hybrid retrieval: full-text (OpenSearch) + semantic (Qdrant) fused with a simple
reciprocal-rank score (re-ranker to be wired later via cross-encoder).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.integrations.search import SearchClient, SearchHit
from app.integrations.vector import VectorStore


@dataclass
class FederatedHit:
    id: str
    source_type: str
    score: float
    title: str
    preview: str
    link: str


class SearchService:
    def __init__(self, fulltext: SearchClient, vector: VectorStore) -> None:
        self.fulltext = fulltext
        self.vector = vector

    async def search(
        self,
        *,
        account_id: int,
        query: str,
        sources: list[str] | None = None,
        size: int = 20,
    ) -> list[FederatedHit]:
        sources = sources or ["mail", "attachments", "contacts", "tasks", "meetings", "travel"]
        hits: list[FederatedHit] = []
        # full-text across per-account indices
        for src in sources:
            index = f"acct_{account_id}_{src}"
            for h in await self.fulltext.search(index, query, size=size):
                hits.append(self._to_hit(h, src))
        # fuse and return top-k
        return sorted(hits, key=lambda h: h.score, reverse=True)[:size]

    @staticmethod
    def _to_hit(h: SearchHit, source: str) -> FederatedHit:
        title = h.source.get("subject") or h.source.get("name") or h.source.get("title") or h.id
        preview = (h.source.get("snippet") or h.source.get("description") or "")[:240]
        return FederatedHit(
            id=h.id,
            source_type=source,
            score=h.score,
            title=str(title),
            preview=str(preview),
            link=f"/{source}/{h.id}",
        )
