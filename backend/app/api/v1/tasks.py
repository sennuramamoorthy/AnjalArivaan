"""Tasks."""
from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_task_service
from app.domain.schemas.task import TaskCreate, TaskOut, TaskStateUpdate
from app.services.task_service import TaskService

router = APIRouter()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: TaskCreate,
    user: CurrentUser,
    svc: TaskService = Depends(get_task_service),
):
    return TaskOut.model_validate(svc.create(user.id, payload))


@router.get("/assigned-to-me", response_model=list[TaskOut])
def mine(
    user: CurrentUser,
    state: str | None = None,
    svc: TaskService = Depends(get_task_service),
):
    return [TaskOut.model_validate(t) for t in svc.list_for_assignee(user.id, state)]


@router.post("/{task_id}/transition", response_model=TaskOut)
def transition(
    task_id: int,
    payload: TaskStateUpdate,
    svc: TaskService = Depends(get_task_service),
):
    return TaskOut.model_validate(svc.transition(task_id, payload.state))
