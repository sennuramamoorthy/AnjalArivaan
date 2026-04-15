"""Mail REST routes — list, detail, thread, mark-read.

Transforms MailMessage domain objects into camelCase JSON matching
the frontend TypeScript types in apps/pwa/lib/api/mail.ts.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.shared.domain.envelope import error_response, success_response

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _get_user(request: Request) -> Optional[dict]:
    """Extract current user via auth_service.verify_access_token."""
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


def _parse_sender(from_address: str) -> tuple[str, str]:
    """Parse 'Name <email>' format. Falls back to email as both name and email."""
    if "<" in from_address and ">" in from_address:
        name = from_address[: from_address.index("<")].strip().strip('"')
        email = from_address[from_address.index("<") + 1 : from_address.index(">")]
        return name or email, email
    # Plain email address — derive a display name from the local part
    local = from_address.split("@")[0] if "@" in from_address else from_address
    display = local.replace(".", " ").replace("_", " ").title()
    return display, from_address


def _to_email_summary(msg) -> dict:
    """Transform MailMessage → frontend EmailSummary (camelCase)."""
    sender_name, sender_email = _parse_sender(msg.from_address)
    return {
        "id": msg.id,
        "threadId": msg.thread_id,
        "from": {"name": sender_name, "email": sender_email},
        "subject": msg.subject,
        "preview": msg.body_text[:150] if msg.body_text else "",
        "receivedAt": msg.received_at.isoformat(),
        "isRead": msg.is_read,
        "urgencyLevel": msg.urgency_level.value,
        "hasAttachment": msg.has_attachment,
        "linkedAccountId": msg.account_id,
        "linkedAccount": msg.account_id,
        "labels": msg.labels,
    }


def _to_email_message(msg) -> dict:
    """Transform MailMessage → frontend EmailMessage (full body, camelCase)."""
    sender_name, sender_email = _parse_sender(msg.from_address)
    to_list = [{"name": addr, "email": addr} for addr in (msg.to_addresses or [])]
    cc_list = [{"name": addr, "email": addr} for addr in (msg.cc_addresses or [])]
    return {
        "id": msg.id,
        "from": {"name": sender_name, "email": sender_email},
        "to": to_list,
        "cc": cc_list,
        "subject": msg.subject,
        "bodyHtml": msg.body_html,
        "bodyText": msg.body_text,
        "receivedAt": msg.received_at.isoformat(),
        "isRead": msg.is_read,
        "hasAttachment": msg.has_attachment,
    }


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/mail")
async def list_mail(
    request: Request,
    accountId: Optional[str] = Query(None),
    folder: str = Query(
        "inbox",
        description="Gmail folder/label slug: inbox|sent|drafts|trash|starred|important|all",
    ),
    filter: str = Query("all"),
    search: str = Query(""),
    sort: str = Query("newest", description="newest|oldest|sender|subject"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    """List emails for an account with folder + cross-cut filtering, search, and pagination."""
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

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    msgs, total = await mail_repo.list_by_account(
        accountId,
        folder=folder,
        filter=filter,
        search=search,
        sort=sort,
        page=page,
        page_size=pageSize,
    )

    emails = [_to_email_summary(m) for m in msgs]
    has_more = (page * pageSize) < total

    return success_response(
        {
            "emails": emails,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": has_more,
        },
        trace_id,
    )


@router.get("/mail/{mail_id}")
async def get_mail(
    mail_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Get a single email by ID."""
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

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    msg = await mail_repo.find_by_id(mail_id, accountId)
    if msg is None:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Mail {mail_id} not found", trace_id),
        )

    return success_response(_to_email_summary(msg), trace_id)


@router.get("/mail/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Get all messages in a thread, ordered by received_at ASC."""
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

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    msgs = await mail_repo.find_thread(thread_id, accountId)
    if not msgs:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Thread {thread_id} not found", trace_id),
        )

    # Use the first message's subject as thread subject
    subject = msgs[0].subject
    # Thread urgency = highest urgency among messages
    urgency_order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    max_urgency = max(msgs, key=lambda m: urgency_order.get(m.urgency_level.value, 0))

    return success_response(
        {
            "id": thread_id,
            "subject": subject,
            "messages": [_to_email_message(m) for m in msgs],
            "urgencyLevel": max_urgency.urgency_level.value,
            "linkedAccount": msgs[0].account_id,
        },
        trace_id,
    )


@router.patch("/mail/threads/{thread_id}/read")
async def mark_thread_read(
    thread_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Mark every message in a thread as read (Gmail-style open-to-read)."""
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

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    updated = await mail_repo.mark_thread_read(thread_id, accountId)
    return success_response({"success": True, "updated": updated}, trace_id)


@router.patch("/mail/{mail_id}/read")
async def mark_read(
    mail_id: str,
    request: Request,
    accountId: Optional[str] = Query(None),
):
    """Mark a message as read."""
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

    mail_repo = getattr(request.app.state, "mail_repo", None)
    if mail_repo is None:
        return JSONResponse(
            status_code=503,
            content=error_response("SERVICE_UNAVAILABLE", "Mail service not available", trace_id),
        )

    updated = await mail_repo.mark_read(mail_id, accountId)
    if not updated:
        return JSONResponse(
            status_code=404,
            content=error_response("NOT_FOUND", f"Mail {mail_id} not found", trace_id),
        )

    return success_response({"success": True}, trace_id)
