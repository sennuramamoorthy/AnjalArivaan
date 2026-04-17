"""Task REST routes.

Per D10 the primary creation channel for tasks is email-driven (on the
mail-sync side). These routes are the supplementary CRUD plumbing used by
the PWA and the admin console. Ownership for a Task is a simple identity
check: ``task.assignee_id == caller.id``. Foreign-task access returns 404
(never 403) to avoid leaking the existence of other users' tasks.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from src.modules.task.repositories.interface import TASK_STATUS_VALUES, Task
from src.shared.domain.envelope import error_response, success_response
from src.shared.domain.errors import ValidationError

router = APIRouter()


# ── Pydantic input models ────────────────────────────────────────────────────

TaskStatus = Literal["OPEN", "IN_PROGRESS", "DONE", "OVERDUE", "CANCELLED"]


class CreateTaskInput(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    due_at: Optional[datetime] = None
    source_mail_id: Optional[str] = None
    # When the caller assigns to somebody else; if omitted we assign to self.
    assignee_id: Optional[str] = None


class UpdateTaskInput(BaseModel):
    subject: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[TaskStatus] = None
    due_at: Optional[datetime] = None


# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _log(request: Request, *, operation: str, **fields) -> None:
    logger = getattr(request.app.state, "logger", None)
    if logger is None:
        return
    try:
        clean = {k: v for k, v in fields.items() if v is not None}
        logger.info(operation, service="tasks", **clean)
    except Exception:
        pass


async def _audit(
    request: Request,
    *,
    actor: str,
    action: str,
    target: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> None:
    audit_repo = getattr(request.app.state, "audit_repo", None)
    if audit_repo is None:
        return
    try:
        await audit_repo.log_event(
            actor=actor,
            action=action,
            target=target,
            before=before,
            after=after,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass


def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "subject": t.subject,
        "description": t.description,
        "status": t.status,
        "dueAt": t.due_at.isoformat() if t.due_at else None,
        "assigneeId": t.assignee_id,
        "assignerId": t.assigner_id,
        "sourceMailId": t.source_mail_id,
        "replyToken": t.reply_token,
    }


def _task_repo(request: Request):
    return getattr(request.app.state, "task_repo", None)


def _unauth(trace_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=error_response("UNAUTHORIZED", "Not authenticated", trace_id),
    )


def _service_unavailable(trace_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_response(
            "SERVICE_UNAVAILABLE", "Task service not available", trace_id
        ),
    )


def _not_found(trace_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_response("NOT_FOUND", "Task not found", trace_id),
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/tasks")
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    trace_id = _trace_id(request)
    started = time.time()
    user = _get_user(request)
    if user is None:
        return _unauth(trace_id)

    repo = _task_repo(request)
    if repo is None:
        return _service_unavailable(trace_id)

    if status is not None and status not in TASK_STATUS_VALUES:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "INVALID_INPUT", f"Invalid status: {status}", trace_id
            ),
        )

    tasks = await repo.list_for_user(user["id"], status=status, limit=limit)
    _log(
        request,
        operation="tasks.list",
        trace_id=trace_id,
        user_id=user["id"],
        duration_ms=int((time.time() - started) * 1000),
        count=len(tasks),
    )
    return success_response([_task_to_dict(t) for t in tasks], trace_id)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    trace_id = _trace_id(request)
    started = time.time()
    user = _get_user(request)
    if user is None:
        return _unauth(trace_id)

    repo = _task_repo(request)
    if repo is None:
        return _service_unavailable(trace_id)

    task = await repo.find_by_id(task_id)
    # Ownership check: foreign tasks return 404, not 403 (no existence leak).
    if task is None or task.assignee_id != user["id"]:
        return _not_found(trace_id)

    _log(
        request,
        operation="tasks.get",
        trace_id=trace_id,
        user_id=user["id"],
        task_id=task_id,
        duration_ms=int((time.time() - started) * 1000),
    )
    return success_response(_task_to_dict(task), trace_id)


@router.post("/tasks")
async def create_task(request: Request):
    trace_id = _trace_id(request)
    started = time.time()
    user = _get_user(request)
    if user is None:
        return _unauth(trace_id)

    repo = _task_repo(request)
    if repo is None:
        return _service_unavailable(trace_id)

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    try:
        payload = CreateTaskInput(**body)
    except PydanticValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", str(e.errors()[0]["msg"]), trace_id),
        )

    try:
        task = await repo.create(
            {
                "subject": payload.subject,
                "description": payload.description,
                "due_at": payload.due_at,
                "source_mail_id": payload.source_mail_id,
                "assignee_id": payload.assignee_id or user["id"],
                "assigner_id": user["id"],
                "status": "OPEN",
            }
        )
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", e.message, trace_id),
        )

    await _audit(
        request,
        actor=user["id"],
        action="TASK_CREATE",
        target=task.id,
        after={
            "subject": task.subject,
            "status": task.status,
            "dueAt": task.due_at.isoformat() if task.due_at else None,
            "sourceMailId": task.source_mail_id,
            "assigneeId": task.assignee_id,
        },
    )

    _log(
        request,
        operation="tasks.create",
        trace_id=trace_id,
        user_id=user["id"],
        task_id=task.id,
        duration_ms=int((time.time() - started) * 1000),
    )
    return success_response(_task_to_dict(task), trace_id)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, request: Request):
    trace_id = _trace_id(request)
    started = time.time()
    user = _get_user(request)
    if user is None:
        return _unauth(trace_id)

    repo = _task_repo(request)
    if repo is None:
        return _service_unavailable(trace_id)

    existing = await repo.find_by_id(task_id)
    # Ownership: foreign tasks return 404 (no existence leak).
    if existing is None or existing.assignee_id != user["id"]:
        return _not_found(trace_id)

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    try:
        payload = UpdateTaskInput(**body)
    except PydanticValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", str(e.errors()[0]["msg"]), trace_id),
        )

    update_data = {
        k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None
    }
    if not update_data:
        return success_response(_task_to_dict(existing), trace_id)

    before = {k: getattr(existing, k, None) for k in update_data.keys()}
    # Normalise datetime serialisation for audit "before"
    before_serialised = {
        k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in before.items()
    }

    try:
        updated = await repo.update(task_id, update_data)
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_INPUT", e.message, trace_id),
        )

    if updated is None:
        return _not_found(trace_id)

    after_serialised = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in update_data.items()
    }

    await _audit(
        request,
        actor=user["id"],
        action="TASK_UPDATE",
        target=task_id,
        before=before_serialised,
        after=after_serialised,
    )

    _log(
        request,
        operation="tasks.update",
        trace_id=trace_id,
        user_id=user["id"],
        task_id=task_id,
        duration_ms=int((time.time() - started) * 1000),
    )
    return success_response(_task_to_dict(updated), trace_id)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request):
    trace_id = _trace_id(request)
    started = time.time()
    user = _get_user(request)
    if user is None:
        return _unauth(trace_id)

    repo = _task_repo(request)
    if repo is None:
        return _service_unavailable(trace_id)

    existing = await repo.find_by_id(task_id)
    if existing is None or existing.assignee_id != user["id"]:
        return _not_found(trace_id)

    deleted = await repo.delete(task_id)
    if not deleted:
        return _not_found(trace_id)

    await _audit(
        request,
        actor=user["id"],
        action="TASK_DELETE",
        target=task_id,
        before={
            "subject": existing.subject,
            "status": existing.status,
            "dueAt": existing.due_at.isoformat() if existing.due_at else None,
        },
    )

    _log(
        request,
        operation="tasks.delete",
        trace_id=trace_id,
        user_id=user["id"],
        task_id=task_id,
        duration_ms=int((time.time() - started) * 1000),
    )
    return success_response({"deleted": True}, trace_id)
