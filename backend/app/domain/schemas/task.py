"""Task DTOs."""
from datetime import datetime

from pydantic import BaseModel

from app.domain.models.task import TaskState
from app.domain.schemas.common import ORMModel


class TaskCreate(BaseModel):
    assignee_user_id: int
    subject: str
    description: str = ""
    due_at: datetime | None = None
    source_mail_id: int | None = None


class TaskStateUpdate(BaseModel):
    state: TaskState


class TaskOut(ORMModel):
    id: int
    assigner_user_id: int
    assignee_user_id: int
    subject: str
    description: str
    due_at: datetime | None
    state: TaskState
    source_mail_id: int | None
    created_at: datetime
    updated_at: datetime
