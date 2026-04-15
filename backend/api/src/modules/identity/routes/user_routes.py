"""User routes — /users/me."""

import uuid

from fastapi import APIRouter, Request

from src.shared.domain.envelope import success_response, error_response

router = APIRouter()


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


@router.get("/users/me")
async def get_me(request: Request):
    trace_id = _trace_id(request)
    user_repo = request.app.state.user_repo

    # Requires authenticated user
    user = getattr(request.state, "user", None)
    if not user:
        return error_response("UNAUTHORIZED", "Not authenticated", trace_id)

    db_user = await user_repo.find_by_id(user["id"])
    if not db_user:
        return error_response("NOT_FOUND", "User not found", trace_id)

    return success_response(
        {
            "id": db_user.id,
            "email": db_user.email,
            "role": db_user.role,
            "status": db_user.status,
            "mfaEnabled": db_user.mfa_enabled,
            "name": db_user.name,
        },
        trace_id,
    )
