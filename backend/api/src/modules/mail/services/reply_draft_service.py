"""ReplyDraftService — generate exactly 3 AI reply drafts for a mail thread.

Given a thread and an intent (acknowledge / agree / decline / custom), this
service fetches the thread from the Mail repo, pulls the active default
signature for the account, assembles a role-aware prompt, invokes the shared
LLM adapter once, and parses the output into three structured drafts.

Design notes:
  - D2: LLM is on-prem only — we invoke `ILLMAdapter.complete`, whose
    production binding is the local vLLM adapter.
  - D16: the route verifies account ownership before calling this service.
  - D22: English-only output — the prompt explicitly pins language.
  - Audit: every invocation writes `AI_REPLY_DRAFTED` with the SHA-256 of the
    assembled prompt so the append-only log can reconstruct intent.
  - Logging: the route emits the structured JSON line with timing; the
    service only constructs + hashes the prompt.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.modules.admin.repositories.audit_repo import IAuditRepository
from src.modules.ai.adapters.llm.interface import ILLMAdapter
from src.modules.identity.repositories.signature_repository import (
    ISignatureRepository,
)
from src.modules.mail.domain.mail_message import MailMessage
from src.modules.mail.repositories.interface import IMailRepository


# ── Domain ──────────────────────────────────────────────────────────────────


class DraftIntent(str, Enum):
    ACKNOWLEDGE = "acknowledge"
    AGREE = "agree"
    DECLINE = "decline"
    CUSTOM = "custom"


_CANONICAL_INTENTS: tuple[DraftIntent, DraftIntent, DraftIntent] = (
    DraftIntent.ACKNOWLEDGE,
    DraftIntent.AGREE,
    DraftIntent.DECLINE,
)


@dataclass
class DraftOption:
    intent: str
    body: str
    signature_id: Optional[str] = None


@dataclass
class DraftBundle:
    drafts: list[DraftOption] = field(default_factory=list)
    model_id: str = ""
    prompt_template_id: str = ""
    duration_ms: float = 0.0
    prompt_hash: str = ""


# Sentinel used by the prompt and parser to delimit drafts in one LLM call.
DRAFT_SEPARATOR = "---DRAFT---"


# ── Service ─────────────────────────────────────────────────────────────────


class ReplyDraftService:
    def __init__(
        self,
        *,
        mail_repo: IMailRepository,
        signature_repo: ISignatureRepository,
        llm_adapter: ILLMAdapter,
        audit_repo: Optional[IAuditRepository] = None,
        model_id: str = "llama-3.1-8b",
        prompt_template_id: str = "reply_draft_v1",
        logger=None,
    ) -> None:
        self._mail_repo = mail_repo
        self._sig_repo = signature_repo
        self._llm = llm_adapter
        self._audit = audit_repo
        self._model_id = model_id
        self._prompt_template_id = prompt_template_id
        self._logger = logger

    async def generate(
        self,
        *,
        thread_id: str,
        account_id: str,
        user_id: str,
        intent: DraftIntent,
        custom_instruction: Optional[str],
        trace_id: str,
    ) -> DraftBundle:
        """Generate 3 drafts for the given intent.

        Raises ValueError("thread not found") if the thread is empty —
        the route translates that to a 404.
        """
        messages = await self._mail_repo.find_thread(thread_id, account_id)
        if not messages:
            raise ValueError(f"Thread {thread_id} not found for account")

        signature = None
        try:
            signature = await self._sig_repo.find_default_for_account(account_id)
        except Exception:
            signature = None

        prompt = self._assemble_prompt(
            messages=messages,
            intent=intent,
            custom_instruction=custom_instruction,
            signature_html=signature.html_template if signature else None,
        )
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        started = time.monotonic()
        raw = await self._llm.complete(prompt=prompt, max_tokens=768, temperature=0.4)
        duration_ms = (time.monotonic() - started) * 1000.0

        drafts = self._parse_drafts(
            raw, signature_id=signature.id if signature else None
        )

        # Audit the call — actor is the app user, target is the thread.
        if self._audit is not None:
            try:
                await self._audit.log_event(
                    actor=user_id,
                    action="AI_REPLY_DRAFTED",
                    target=thread_id,
                    after={
                        "intent": intent.value,
                        "account_id": account_id,
                        "drafts_generated": len(drafts),
                        "model_id": self._model_id,
                        "prompt_template_id": self._prompt_template_id,
                        "trace_id": trace_id,
                    },
                    content_hash=prompt_hash,
                )
            except Exception:
                # Audit must never take the request down. The JSON log line
                # the route emits is the backup signal.
                pass

        if self._logger is not None:
            try:
                self._logger.info(
                    "mail.ai_reply_drafted",
                    trace_id=trace_id,
                    thread_id=thread_id,
                    account_id=account_id,
                    user_id=user_id,
                    intent=intent.value,
                    model_id=self._model_id,
                    prompt_template_id=self._prompt_template_id,
                    drafts_generated=len(drafts),
                    duration_ms=round(duration_ms, 2),
                )
            except Exception:
                pass

        return DraftBundle(
            drafts=drafts,
            model_id=self._model_id,
            prompt_template_id=self._prompt_template_id,
            duration_ms=duration_ms,
            prompt_hash=prompt_hash,
        )

    # ── Prompt assembly ─────────────────────────────────────────────────

    def _assemble_prompt(
        self,
        *,
        messages: list[MailMessage],
        intent: DraftIntent,
        custom_instruction: Optional[str],
        signature_html: Optional[str],
    ) -> str:
        """Build the single-shot prompt that asks the LLM for 3 drafts.

        Kept deliberately compact — the mock adapter ignores the prompt, and
        the real adapter will re-template upstream. The one guarantee we need
        is that user-provided `custom_instruction` is embedded verbatim so the
        unit test can assert it is respected.
        """
        header = (
            "You are an executive assistant drafting email replies for a "
            "Tamil-Nadu university dean. Output English only."
        )
        thread_lines: list[str] = []
        for m in messages[-5:]:  # last 5 messages are enough context in Phase 1a
            thread_lines.append(
                f"From: {m.from_address}\nSubject: {m.subject}\n\n{m.body_text}\n---"
            )
        thread_block = "\n".join(thread_lines)

        if intent == DraftIntent.CUSTOM:
            intent_block = (
                "Produce three candidate replies that follow the user's "
                f"custom instruction: {custom_instruction or ''}"
            )
        else:
            intent_block = (
                "Produce three candidate replies: (1) acknowledge receipt, "
                "(2) agree / confirm action, (3) decline politely."
                f" Primary intent the user will most likely pick: {intent.value}."
            )

        sig_block = (
            f"\nSignature to append (plain text):\n{signature_html}\n"
            if signature_html
            else ""
        )

        return (
            f"{header}\n\n"
            f"Thread:\n{thread_block}\n\n"
            f"Task: {intent_block}\n"
            f"Separate each draft with a line containing only '{DRAFT_SEPARATOR}'."
            f"{sig_block}"
        )

    # ── Output parsing ──────────────────────────────────────────────────

    def _parse_drafts(
        self, raw: str, *, signature_id: Optional[str]
    ) -> list[DraftOption]:
        """Split LLM output on DRAFT_SEPARATOR and pad/trim to exactly 3.

        If the model returns fewer than 3, we repeat the last one; if more,
        we keep the first three. Every draft is associated with a canonical
        intent label (acknowledge / agree / decline) in order — this lets
        the PWA render intent-labeled chips without a second round-trip.
        """
        parts = [p.strip() for p in (raw or "").split(DRAFT_SEPARATOR)]
        parts = [p for p in parts if p]
        if not parts:
            parts = ["(The assistant could not produce a draft — please try again.)"]

        # Normalise to exactly 3.
        while len(parts) < 3:
            parts.append(parts[-1])
        parts = parts[:3]

        return [
            DraftOption(
                intent=_CANONICAL_INTENTS[i].value,
                body=body,
                signature_id=signature_id,
            )
            for i, body in enumerate(parts)
        ]
