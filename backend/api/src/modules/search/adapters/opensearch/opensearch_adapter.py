"""OpenSearchAdapter — real BM25 backend (opensearch-py).

Per-account indices (D16): ``mail-{account_id}``, ``attachments-{account_id}``.
The adapter NEVER issues a query that spans accounts — the only way to
target more than one index in a call is ``filters['type'] == 'all'``, which
expands to the current account's mail + attachment indices ONLY.
"""

from __future__ import annotations

from typing import Any

from src.modules.search.adapters.opensearch.interface import ISearchIndex


def _mail_index(account_id: str) -> str:
    return f"mail-{account_id}"


def _attachment_index(account_id: str) -> str:
    return f"attachments-{account_id}"


def _index_for(account_id: str, doc_type: str) -> str:
    if doc_type == "attachment":
        return _attachment_index(account_id)
    return _mail_index(account_id)


class OpenSearchAdapter(ISearchIndex):
    """Thin wrapper around ``opensearchpy.OpenSearch``.

    The client is injected so tests can swap in a fake. In production the
    client is constructed in ``app.py`` wiring with the cluster URL + TLS
    config from settings.
    """

    def __init__(self, *, client: Any, logger: Any | None = None) -> None:
        self._client = client
        self._logger = logger

    # ── Write path ────────────────────────────────────────────────────

    async def index_document(self, account_id: str, doc: dict[str, Any]) -> None:
        doc_type = doc.get("type", "mail")
        index = _index_for(account_id, doc_type)
        doc_id = doc["id"]
        # NB: opensearch-py is sync — these methods aren't actually async,
        # but we wrap in `async def` to keep the adapter contract uniform.
        self._client.index(index=index, id=doc_id, body=doc, refresh=False)

    async def delete_document(
        self, account_id: str, doc_id: str, *, doc_type: str = "mail"
    ) -> None:
        index = _index_for(account_id, doc_type)
        self._client.delete(index=index, id=doc_id, ignore=(404,))

    # ── Read path ─────────────────────────────────────────────────────

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

        indices: list[str]
        if doc_type == "mail":
            indices = [_mail_index(account_id)]
        elif doc_type == "attachment":
            indices = [_attachment_index(account_id)]
        else:  # "all" — still strictly scoped to this one account (D16)
            indices = [_mail_index(account_id), _attachment_index(account_id)]

        body = {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["subject^2", "body", "filename^2", "ocr_text"],
                }
            },
            "highlight": {"fields": {"subject": {}, "body": {}, "ocr_text": {}}},
        }

        hits: list[dict[str, Any]] = []
        for index in indices:
            # Skip indices that don't exist yet — fresh account, never synced.
            try:
                if hasattr(self._client, "indices_exists") and not self._client.indices_exists(index):
                    continue
            except Exception:
                pass

            try:
                resp = self._client.search(index=index, body=body)
            except Exception as exc:  # noqa: BLE001
                if self._logger is not None:
                    self._logger.warn(
                        "opensearch.search_error",
                        index=index,
                        error=str(exc),
                    )
                continue

            for h in resp.get("hits", {}).get("hits", []):
                hits.append(
                    {
                        "id": h["_id"],
                        "score": h["_score"],
                        "source": h["_source"],
                        "index": index,
                    }
                )

        # Sort merged by score desc, trim to limit.
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:limit]
