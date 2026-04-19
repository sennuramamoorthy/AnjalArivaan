"""Full-text search port (OpenSearch) + stub."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class SearchHit:
    id: str
    score: float
    source: dict


class SearchClient(Protocol):
    async def index(self, index: str, doc_id: str, body: dict) -> None: ...
    async def search(self, index: str, query: str, size: int = 20) -> list[SearchHit]: ...


class InMemorySearchClient(SearchClient):
    """Trivial keyword matcher for tests (no real tokenization / stemming)."""

    def __init__(self) -> None:
        self._idx: dict[str, dict[str, dict]] = {}

    async def index(self, index: str, doc_id: str, body: dict) -> None:
        self._idx.setdefault(index, {})[doc_id] = body

    async def search(self, index: str, query: str, size: int = 20) -> list[SearchHit]:
        q = query.lower()
        hits: list[SearchHit] = []
        for doc_id, body in self._idx.get(index, {}).items():
            haystack = " ".join(str(v).lower() for v in body.values() if isinstance(v, (str, int, float)))
            if q in haystack:
                score = haystack.count(q) / max(1, len(haystack.split()))
                hits.append(SearchHit(id=doc_id, score=score, source=body))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:size]
