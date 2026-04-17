"""
MailSyncService — orchestrates Gmail sync, storage, and event publishing.

All external I/O goes through adapter interfaces; no direct SDK calls here.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from src.modules.mail.adapters.gmail.interface import IGmailAdapter
from src.modules.mail.adapters.messaging.interface import IMessageBus
from src.modules.mail.adapters.storage.interface import IObjectStorage
from src.modules.mail.adapters.vault.interface import IVaultAdapter
from src.modules.mail.domain.attachment import Attachment
from src.modules.mail.domain.events import AttachmentReadyEvent, NewMailEvent
from src.modules.mail.domain.mail_message import MailMessage
from src.modules.mail.repositories.interface import IMailRepository
from src.modules.mail.services.message_parser import GmailMessageParser


class MailSyncService:
    """
    Core sync orchestrator.

    Responsibilities:
    1. Fetch an access token from Vault (per-account).
    2. List new messages from the Gmail API.
    3. For each message:
       a. Skip if already synced (idempotency).
       b. Parse raw Gmail response → domain objects.
       c. Persist MailMessage to the repository.
       d. Upload attachments to MinIO.
       e. Publish ``mail.new`` and ``attachment.ready`` events to the outbox.
    """

    def __init__(
        self,
        gmail_adapter: IGmailAdapter,
        vault_adapter: IVaultAdapter,
        mail_repo: IMailRepository,
        object_storage: IObjectStorage,
        message_bus: IMessageBus,
        logger: Any,
        vector_store: Any = None,
        embedding_adapter: Any = None,
        urgency_hook: Any = None,
        search_indexing_service: Any = None,
    ) -> None:
        self._gmail = gmail_adapter
        self._vault = vault_adapter
        self._repo = mail_repo
        self._storage = object_storage
        self._bus = message_bus
        self._logger = logger
        self._parser = GmailMessageParser()
        # Optional D16-scoped embedding pipeline. When either dep is missing
        # we skip embedding work silently and rely on OpenSearch for retrieval.
        self._vector_store = vector_store
        self._embedding_adapter = embedding_adapter
        # Optional urgency-detection hook. Must expose an async
        # ``on_new_mail(mail, account_id, user_id, trace_id)`` method. When
        # unwired, mail sync just publishes the mail.new event and the
        # (legacy) event handler does urgency work. When wired, sync also
        # writes an urgency_outbox row synchronously so the Celery worker
        # can dispatch WhatsApp + line-manager forward independently.
        self._urgency_hook = urgency_hook
        # Optional hybrid-search indexing service. Feeds each new message
        # into per-account OpenSearch + Qdrant indices (D16). Failures are
        # swallowed inside the service so sync continues unaffected.
        self._search_indexing = search_indexing_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_account(
        self, account_id: str, user_id: str, trace_id: str
    ) -> int:
        """
        Sync all new messages for an account.

        Returns the count of newly synced messages.
        """
        log = self._logger.child(account_id=account_id, user_id=user_id, trace_id=trace_id)
        log.info("sync_account.start")

        try:
            access_token = await self._vault.get_access_token(account_id)
        except Exception as exc:
            log.error("sync_account.vault_error", error=exc)
            return 0

        # Paginate through the Gmail message list so folders like Sent /
        # Important / Trash get populated even on busy accounts — the first
        # 50 results are almost always dominated by Inbox. Cap total pulled
        # messages so the initial sync doesn't run unbounded for very large
        # mailboxes; later incremental syncs pick up anything missed.
        MAX_INITIAL_MESSAGES = 500
        PAGE_SIZE = 100

        synced_count = 0
        page_token: str | None = None
        seen_msg_ids: set[str] = set()

        while len(seen_msg_ids) < MAX_INITIAL_MESSAGES:
            with log.timed("gmail.list_messages", account_id=account_id):
                response = await self._gmail.list_messages(
                    access_token,
                    max_results=PAGE_SIZE,
                    page_token=page_token,
                    include_spam_trash=True,
                )

            raw_msgs = response.get("messages", []) or []
            if not raw_msgs and not seen_msg_ids:
                log.info("sync_account.no_messages")
                return 0

            for msg_ref in raw_msgs:
                gmail_msg_id = msg_ref["id"]
                if gmail_msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(gmail_msg_id)
                result = await self.sync_message(
                    account_id=account_id,
                    user_id=user_id,
                    gmail_msg_id=gmail_msg_id,
                    trace_id=trace_id,
                    access_token=access_token,
                )
                if result is not None:
                    synced_count += 1
                if len(seen_msg_ids) >= MAX_INITIAL_MESSAGES:
                    break

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        log.info(
            "sync_account.complete",
            synced_count=synced_count,
            seen=len(seen_msg_ids),
        )
        return synced_count

    async def sync_message(
        self,
        account_id: str,
        user_id: str,
        gmail_msg_id: str,
        trace_id: str,
        access_token: str | None = None,
    ) -> MailMessage | None:
        """
        Sync a single message by Gmail message ID.

        Returns None if the message was already synced (idempotent).
        """
        log = self._logger.child(
            account_id=account_id,
            user_id=user_id,
            gmail_msg_id=gmail_msg_id,
            trace_id=trace_id,
        )

        if await self._repo.exists(gmail_msg_id, account_id):
            log.info("sync_message.skip_duplicate")
            return None

        if access_token is None:
            access_token = await self._vault.get_access_token(account_id)

        with log.timed("gmail.get_message", gmail_msg_id=gmail_msg_id):
            raw = await self._gmail.get_message(access_token, gmail_msg_id)

        mail, attachments = self._parser.parse(raw, account_id)

        with log.timed("repo.save_mail", mail_id=mail.id):
            await self._repo.save(mail)

        # Best-effort embedding + Qdrant upsert. No-ops if either dep is
        # unwired. D16: always targets the mail's own account collection.
        await self._maybe_upsert_embedding(mail, log)

        # Best-effort BM25 + hybrid indexing. The indexing service owns
        # its own try/except so sync continues even if OpenSearch is down
        # (backfill job deferred to Phase 1b).
        if self._search_indexing is not None:
            try:
                await self._search_indexing.index_message(mail.account_id, mail)
            except Exception as exc:  # noqa: BLE001
                log.warn("sync_message.search_index_skipped", error=str(exc))

        await self._handle_attachments(
            message=mail,
            attachments=attachments,
            access_token=access_token,
            trace_id=trace_id,
            user_id=user_id,
        )

        await self._publish_new_mail_event(mail, user_id, trace_id)

        # Run urgency detection inline (same unit-of-work as the mail save)
        # so the outbox row is created iff the mail is persisted. Any
        # exception here is swallowed — an urgency failure must never
        # block mail sync (D1: Gmail is the system of record).
        if self._urgency_hook is not None:
            try:
                await self._urgency_hook.on_new_mail(
                    mail=mail,
                    account_id=account_id,
                    user_id=user_id,
                    trace_id=trace_id,
                )
            except Exception as exc:  # noqa: BLE001
                log.warn("urgency_hook.failed", mail_id=mail.id, error=str(exc))

        log.info("sync_message.complete", mail_id=mail.id)
        return mail

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_attachments(
        self,
        message: MailMessage,
        attachments: list[Attachment],
        access_token: str,
        trace_id: str,
        user_id: str,
    ) -> None:
        """Download and upload each attachment to MinIO, then publish attachment.ready events."""
        for att in attachments:
            log = self._logger.child(
                account_id=message.account_id,
                mail_id=message.id,
                attachment_id=att.id,
                trace_id=trace_id,
            )
            try:
                with log.timed("gmail.get_attachment", attachment_id=att.gmail_attachment_id):
                    data = await self._gmail.get_attachment(
                        access_token, message.gmail_msg_id, att.gmail_attachment_id
                    )

                minio_key = f"{message.account_id}/{message.gmail_msg_id}/{att.filename}"
                with log.timed("minio.upload", key=minio_key):
                    await self._storage.upload(
                        bucket="attachments",
                        key=minio_key,
                        data=data,
                        content_type=att.mime_type,
                    )

                att.minio_key = minio_key
                await self._publish_attachment_ready_event(
                    att, message, user_id, trace_id
                )
            except Exception as exc:
                log.error("handle_attachment.error", error=exc, filename=att.filename)

    async def _publish_new_mail_event(
        self, mail: MailMessage, user_id: str, trace_id: str
    ) -> None:
        event = NewMailEvent(
            account_id=mail.account_id,
            user_id=user_id,
            trace_id=trace_id,
            mail_id=mail.id,
            gmail_msg_id=mail.gmail_msg_id,
            thread_id=mail.thread_id,
            from_address=mail.from_address,
            subject=mail.subject,
            received_at=mail.received_at.isoformat(),
            has_attachment=mail.has_attachment,
        )
        with self._logger.timed(
            "outbox.publish", topic="mail-events", event_type="mail.new"
        ):
            await self._bus.publish("mail-events", dataclasses.asdict(event))

    async def _publish_attachment_ready_event(
        self,
        att: Attachment,
        mail: MailMessage,
        user_id: str,
        trace_id: str,
    ) -> None:
        event = AttachmentReadyEvent(
            account_id=mail.account_id,
            user_id=user_id,
            trace_id=trace_id,
            attachment_id=att.id,
            mail_id=mail.id,
            minio_key=att.minio_key,
            mime_type=att.mime_type,
        )
        with self._logger.timed(
            "outbox.publish", topic="attachment-events", event_type="attachment.ready"
        ):
            await self._bus.publish("attachment-events", dataclasses.asdict(event))

    async def _maybe_upsert_embedding(
        self,
        mail: MailMessage,
        log: Any,
    ) -> None:
        """Embed the mail body and upsert to Qdrant, if both deps are wired.

        D16 guarantee: the upsert is scoped to `collection_name = mail.account_id`
        and the `ChunkEmbedding.account_id == mail.account_id`, so the
        vector-store adapter's isolation guard can never fire for a correctly
        assembled mail.

        No-ops if the vector store or embedding adapter isn't configured —
        these are Phase 1a additive features and the mail-sync path must
        keep working even when Qdrant is unreachable.
        """
        if self._vector_store is None or self._embedding_adapter is None:
            return

        try:
            from src.modules.ai.domain.embedding import ChunkEmbedding

            # A single whole-message embedding is sufficient for Phase 1a;
            # chunk-level splitting is a Phase 1b concern.
            body = (mail.subject or "") + "\n\n" + (getattr(mail, "body_text", "") or "")
            if not body.strip():
                return
            vector = await self._embedding_adapter.embed(body)
            chunk = ChunkEmbedding(
                chunk_id=f"{mail.id}:0",
                account_id=mail.account_id,
                mail_id=mail.id,
                text=body[:4000],
                vector=vector,
                metadata={"source_mail_id": mail.id},
            )
            await self._vector_store.upsert_chunks(mail.account_id, [chunk])
            log.info("sync_message.embedding_upserted", mail_id=mail.id)
        except Exception as exc:  # noqa: BLE001
            # Best-effort: log and continue. Sync must not fail because
            # embedding failed — OpenSearch still provides full-text retrieval.
            log.warn(
                "sync_message.embedding_skipped",
                mail_id=mail.id,
                error=str(exc),
            )
