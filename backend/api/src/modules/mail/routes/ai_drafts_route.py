"""POST /api/v1/mail/threads/{threadId}/ai-drafts — multi-intent drafts.

Distinct from the existing single-draft endpoint at /ai-draft (singular), this
route returns THREE structured drafts for the same thread so the PWA can show
acknowledge / agree / decline chips in one round-trip.

Body:
    { "intent": "acknowledge" | "agree" | "decline" | "custom",
      "customInstruction": "..."   # required when intent=custom }

Response:
    { "drafts": [ { "intent": "acknowledge", "body": "...", "signatureId": "sig-1" }, ... ] }
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from src.modules.mail.services.reply_draft_service import (
    DraftIntent,
    ReplyDraftService,
)
from src.shared.domain.envelope import error_response, success_response
from src.shared.middleware.account_ownership import require_account_ownership

router = APIRouter()


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return None
    try:
        payload = auth_service.verify_access_token(token)
        return {
            "id": payload["sub"],
            "email": payload["email"],
            "role": payload["role"],
        }
    except Exception:
        return None


def _log(request: Request, **fields) -> None:
    logger = getattr(request.app.state, "logger", None)
    if logger is None:
        return
    try:
        logger.info("mail.ai_reply_drafted.route", **{k: v for k, v in fields.items() if v is not None})
    except Exception:
        pass


@router.post("/mail/threads/{thread_id}/ai-drafts")
async def ai_drafts(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
    payload: dict = Body(default_factory=dict),
):
    trace_id = _trace_id(request)

    # 1. Authn
    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    # 2. Validate accountId param
    if not accountId:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST", "accountId query parameter is required", trace_id
            ),
        )

    # 3. Parse + validate intent BEFORE touching ownership so bad payloads
    #    get a deterministic 400.
    raw_intent = (payload or {}).get("intent") if isinstance(payload, dict) else None
    custom_instruction = (
        (payload or {}).get("customInstruction") if isinstance(payload, dict) else None
    )
    try:
        intent = DraftIntent(raw_intent) if raw_intent else None
    except ValueError:
        intent = None
    if intent is None:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST",
                "intent must be one of: acknowledge, agree, decline, custom",
                trace_id,
            ),
        )
    if intent == DraftIntent.CUSTOM and not (custom_instruction or "").strip():
        return JSONResponse(
            status_code=400,
            content=error_response(
                "BAD_REQUEST",
                "customInstruction is required when intent=custom",
                trace_id,
            ),
        )

    # 4. D16 per-account isolation.
    forbidden = await require_account_ownership(request, accountId, user["id"], trace_id)
    if forbidden:
        return forbidden

    # 5. Resolve service — the app wires either a real or test-injected one.
    service: Optional[ReplyDraftService] = getattr(
        request.app.state, "reply_draft_service", None
    )
    if service is None:
        return JSONResponse(
            status_code=503,
            content=error_response(
                "SERVICE_UNAVAILABLE", "AI reply draft service not available", trace_id
            ),
        )

    started = time.monotonic()
    try:
        bundle = await service.generate(
            thread_id=thread_id,
            account_id=accountId,
            user_id=user["id"],
            intent=intent,
            custom_instruction=custom_instruction,
            trace_id=trace_id,
        )
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Thread {thread_id} not found", trace_id),
        )
    duration_ms = round((time.monotonic() - started) * 1000.0, 2)

    _log(
        request,
        trace_id=trace_id,
        thread_id=thread_id,
        account_id=accountId,
        user_id=user["id"],
        intent=intent.value,
        model_id=bundle.model_id,
        prompt_template_id=bundle.prompt_template_id,
        drafts_generated=len(bundle.drafts),
        duration_ms=duration_ms,
    )

    return success_response(
        {
            "drafts": [
                {
                    "intent": d.intent,
                    "body": d.body,
                    "signatureId": d.signature_id,
                }
                for d in bundle.drafts
            ],
            "modelId": bundle.model_id,
            "promptTemplateId": bundle.prompt_template_id,
        },
        trace_id,
    )
