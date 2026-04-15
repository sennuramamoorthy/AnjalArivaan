"""
pubsub_webhook.py — FastAPI route for receiving Gmail push notifications.

Google Cloud Pub/Sub pushes base64-encoded JSON payloads to this endpoint.
The route MUST always return HTTP 200 to ACK the message; otherwise Pub/Sub
will redeliver it indefinitely.  Actual sync work is delegated to a background
task so the response is immediate.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

router = APIRouter()

_log = logging.getLogger("mail-sync.webhook")


# ---------------------------------------------------------------------------
# Pydantic models for the Pub/Sub push payload
# ---------------------------------------------------------------------------

class PubSubMessage(BaseModel):
    data: str           # base64-encoded JSON
    messageId: str
    publishTime: str
    attributes: dict[str, str] = {}


class PubSubRequest(BaseModel):
    message: PubSubMessage
    subscription: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/webhooks/pubsub")
async def handle_pubsub_push(
    request_body: PubSubRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, str]:
    """
    Receives Gmail push notifications from Google Cloud Pub/Sub.

    Decodes the Pub/Sub message, extracts the account_id, and schedules
    a background sync.  Always returns ``{"status": "ok"}`` to ACK.
    """
    sync_service = request.app.state.sync_service

    try:
        payload = _decode_pubsub_data(request_body.message.data)
        # accountId may come from attributes (preferred) or we derive it later
        account_id: str = (
            request_body.message.attributes.get("accountId")
            or payload.get("emailAddress", "unknown")
        )
        history_id: str = str(payload.get("historyId", ""))
        trace_id: str = request_body.message.messageId

        background_tasks.add_task(
            _run_sync,
            sync_service=sync_service,
            account_id=account_id,
            history_id=history_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        # Log but do NOT re-raise — we still return 200 to prevent redelivery
        _log.error("pubsub_webhook.decode_error: %s", exc)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_pubsub_data(data: str) -> dict[str, Any]:
    """Decode the base64url-encoded Pub/Sub message data field."""
    # Add padding if necessary
    padded = data + "=="
    raw = base64.urlsafe_b64decode(padded)
    return json.loads(raw)


async def _run_sync(
    sync_service: Any,
    account_id: str,
    history_id: str,
    trace_id: str,
) -> None:
    """Background task: call sync_service and swallow exceptions."""
    try:
        await sync_service.sync_account(
            account_id=account_id,
            user_id="",          # Webhook path resolves user from account_id in service
            trace_id=trace_id,
        )
    except Exception as exc:
        _log.error(
            "pubsub_webhook.sync_error: account_id=%s trace_id=%s error=%s",
            account_id, trace_id, exc,
        )
