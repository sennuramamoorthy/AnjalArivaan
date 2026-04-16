"""Account-lifecycle hooks for the AI module.

Keep this module dependency-light: it is imported by the account-link OAuth
callback, which must never fail to link a user just because the vector store
is momentarily unavailable. All helpers swallow vector-store errors and log
a warning, so the happy-path user experience is unaffected by Qdrant outages.
"""

from __future__ import annotations

from typing import Any

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter


async def ensure_account_vector_namespace(
    account_id: str,
    vector_store: IVectorStoreAdapter | None,
    logger: Any | None = None,
) -> bool:
    """Idempotently create the per-account Qdrant collection.

    Returns True on success (including "already existed"), False on failure
    or when no vector store is wired. Never raises — the account-link flow
    must tolerate Qdrant being down.
    """
    if vector_store is None:
        if logger:
            logger.warn(
                "account_lifecycle.ensure_namespace.skipped",
                reason="vector_store not wired",
                account_id=account_id,
            )
        return False

    try:
        await vector_store.ensure_collection(account_id)
        if logger:
            logger.info(
                "account_lifecycle.ensure_namespace.ok",
                account_id=account_id,
            )
        return True
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warn(
                "account_lifecycle.ensure_namespace.failed",
                account_id=account_id,
                error=str(exc),
            )
        return False


async def delete_account_vector_namespace(
    account_id: str,
    vector_store: IVectorStoreAdapter | None,
    logger: Any | None = None,
) -> bool:
    """Drop the per-account collection on revoke. Never raises."""
    if vector_store is None:
        return False
    try:
        await vector_store.delete_account_data(account_id)
        if logger:
            logger.info(
                "account_lifecycle.delete_namespace.ok",
                account_id=account_id,
            )
        return True
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warn(
                "account_lifecycle.delete_namespace.failed",
                account_id=account_id,
                error=str(exc),
            )
        return False
