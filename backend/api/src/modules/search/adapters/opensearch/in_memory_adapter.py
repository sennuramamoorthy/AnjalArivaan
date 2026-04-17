"""InMemorySearchAdapter — dict-backed ISearchIndex for tests and dev.

Honours per-account index isolation (D16) in the same way as the real
adapter: storage is keyed by a derived ``mail-{account_id}`` /
``attachments-{account_id}`` bucket name, so the only way to read a doc is
via its owning account.
"""

from __future__ import annotations

from typing import Any

from src.modules.search.adapters.opensearch.interface import ISearchIndex


def _bucket(account_id: str, doc_type: str) -> str:
    return f"{'attachments' if doc_type == 'attachment' else 'mail'}-{account_id}"


class InMemorySearchAdapter(ISearchIndex):
    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, dict[str, Any]]] = {}

    async def index_document(self, account_id: str, doc: dict[str, Any]) -> None:
        doc_type = doc.get("type", "mail")
        bucket = _bucket(account_id, doc_type)
        self._buckets.setdefault(bucket, {})[doc["id"]] = dict(doc)

    async def delete_document(
        self, account_id: str, doc_id: str, *, doc_type: str = "mail"
    ) -> None:
        bucket = _bucket(account_id, doc_type)
        self._buckets.get(bucket, {}).pop(doc_id, None)

    async def search(
        self,
        *,
        query: str,
        account_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        doc_type = filters.get("type", "all")

        buckets: list[str]
        if doc_type == "mail":
            buckets = [_bucket(account_id, "mail")]
        elif doc_type == "attachment":
            buckets = [_bucket(account_id, "attachment")]
        else:
            buckets = [
                _bucket(account_id, "mail"),
                _bucket(account_id, "attachment"),
            ]

        q = (query or "").strip().lower()
        hits: list[dict[str, Any]] = []
        for bname in buckets:
            for doc_id, src in self._buckets.get(bname, {}).items():
                # Cheap BM25 stand-in: case-insensitive substring match on
                # any searchable field, score = term frequency.
                blob = " ".join(
                    str(v)
                    for k, v in src.items()
                    if k in ("subject", "body", "filename", "ocr_text")
                ).lower()
                if q and q in blob:
                    hits.append(
                        {
                            "id": doc_id,
                            "score": float(blob.count(q)),
                            "source": src,
                            "index": bname,
                        }
                    )

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:limit]
