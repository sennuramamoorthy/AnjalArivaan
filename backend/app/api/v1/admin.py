"""Admin console endpoints (PRD §3.14)."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import _users, require_super_admin
from app.domain.schemas.auth import UserOut
from app.repositories.user import AppUserRepository

router = APIRouter()


@router.get(
    "/users", response_model=list[UserOut], dependencies=[Depends(require_super_admin)]
)
def list_users(
    limit: int = 100, offset: int = 0, repo: AppUserRepository = Depends(_users)
):
    return [UserOut.model_validate(u) for u in repo.list(limit=limit, offset=offset)]


@router.post(
    "/users/{user_id}/promote-super-admin",
    response_model=UserOut,
    dependencies=[Depends(require_super_admin)],
)
def promote_super(user_id: int, repo: AppUserRepository = Depends(_users)):
    u = repo.get(user_id)
    if not u:
        raise HTTPException(status_code=404)
    u.is_super_admin = True
    repo.commit()
    return UserOut.model_validate(u)


@router.post(
    "/users/{user_id}/promote-dept-admin",
    response_model=UserOut,
    dependencies=[Depends(require_super_admin)],
)
def promote_dept(user_id: int, repo: AppUserRepository = Depends(_users)):
    u = repo.get(user_id)
    if not u:
        raise HTTPException(status_code=404)
    u.is_dept_admin = True
    repo.commit()
    return UserOut.model_validate(u)
