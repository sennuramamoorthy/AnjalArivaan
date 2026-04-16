"""Mail send routes — reply / reply-all / forward via Gmail send API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

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
        return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
    except Exception:
        return None


def _build_rfc2822(
    *,
    from_addr: str,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    body_text: str,
    body_html: str | None,
    in_reply_to: str | None,
    references: list[str] | None,
) -> str:
    """Build a well-formed RFC-2822 message string."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to) if to else ""
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)

    msg.set_content(body_text or "")
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg.as_string()


@router.post("/mail/threads/{thread_id}/send")
async def send_reply(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
    payload: dict = Body(...),
):
    """
    Send a reply / reply-all / forward message. The payload carries the
    editable fields:

        {
          "to":      ["addr", ...],
          "cc":      ["addr", ...],
          "bcc":     ["addr", ...],
          "subject": "Re: ...",
          "bodyText": "...",
          "bodyHtml": "<p>...</p>",         # optional
          "mode":    "reply"|"replyAll"|"forward",
          "inReplyTo": "<message-id>",      # RFC-822 Message-ID of the email being replied to
          "references": ["<msg-id>", ...]   # thread chain
        }
    """
    trace_id = _trace_id(request)

    user = _get_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
        )

    if not accountId:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "accountId query parameter is required", trace_id),
        )

    to = [a for a in (payload.get("to") or []) if a]
    cc = [a for a in (payload.get("cc") or []) if a]
    bcc = [a for a in (payload.get("bcc") or []) if a]
    subject = (payload.get("subject") or "").strip()
    body_text = payload.get("bodyText") or ""
    body_html = payload.get("bodyHtml")
    in_reply_to = payload.get("inReplyTo")
    references = payload.get("references") or []

    if not to:
        return JSONResponse(
            status_code=400,
            content=error_response("BAD_REQUEST", "At least one recipient is required", trace_id),
        )

    gmail_adapter = getattr(request.app.state, "gmail_adapter", None)
    vault_adapter = getattr(request.app.state, "mail_vault_adapter", None)
    linked_repo = getattr(request.app.state, "linked_account_repo", None)
    if gmail_adapter is None or vault_adapter is None or linked_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Send service not available", trace_id),
        )

    # D16: refuse sends when accountId does not belong to the caller.
    forbidden = await require_account_ownership(request, accountId, user["id"], trace_id)
    if forbidden:
        return forbidden

    # Already ownership-checked; fetch again here because we need the google_email.
    account = await linked_repo.find_by_id(accountId)
    from_addr = getattr(account, "google_email", None) or user["email"]

    # ── Auto-append default signature for this account ─────────────
    sig_repo = getattr(request.app.state, "signature_repo", None)
    if sig_repo is not None:
        try:
            default_sig = await sig_repo.find_default_for_account(accountId)
        except Exception:
            default_sig = None
        if default_sig and default_sig.html_template:
            sig_text = default_sig.html_template
            body_text = body_text.rstrip() + "\n\n--\n" + sig_text
            if body_html:
                body_html = body_html + "<br><br>--<br>" + sig_text.replace("\n", "<br>")

    access_token = await vault_adapter.get_access_token(accountId)

    raw = _build_rfc2822(
        from_addr=from_addr,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        in_reply_to=in_reply_to,
        references=references,
    )

    try:
        result = await gmail_adapter.send_message(
            access_token, raw, thread_id=thread_id if thread_id != "new" else None
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content=error_response("SEND_FAILED", f"Gmail send failed: {exc}", trace_id),
        )

    # ── Store sent message locally so it appears in the Sent folder ──
    gmail_msg_id = result.get("id", str(uuid.uuid4()))
    result_thread_id = result.get("threadId", thread_id)

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo:
        from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel

        sent_msg = MailMessage(
            id=str(uuid.uuid4()),
            account_id=accountId,
            gmail_msg_id=gmail_msg_id,
            thread_id=result_thread_id,
            from_address=from_addr,
            to_addresses=to,
            cc_addresses=cc,
            subject=subject,
            body_text=body_text,
            body_html=body_html or "",
            received_at=datetime.now(timezone.utc),
            labels=["SENT"],
            has_attachment=False,
            urgency_level=UrgencyLevel.NONE,
            urgency_score=0.0,
            is_read=True,
        )
        try:
            await mail_repo.save(sent_msg)
        except Exception:
            # Non-fatal — message sent via Gmail; local copy is best-effort
            pass

    return success_response(
        {
            "success": True,
            "messageId": gmail_msg_id,
            "threadId": result_thread_id,
        },
        trace_id,
    )
