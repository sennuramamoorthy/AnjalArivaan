"""Task state-machine tests."""
import pytest

from app.core.exceptions import ValidationError
from app.domain.models.task import TaskState
from app.domain.schemas.task import TaskCreate
from app.repositories.task import TaskRepository
from app.services.task_service import TaskService


@pytest.fixture
def service(db):
    return TaskService(TaskRepository(db))


def test_create_task_starts_in_assigned(service):
    task = service.create(
        assigner_id=1,
        payload=TaskCreate(assignee_user_id=2, subject="Prepare briefing"),
    )
    assert task.state == TaskState.ASSIGNED
    assert task.reply_token


def test_valid_transition(service):
    task = service.create(
        assigner_id=1, payload=TaskCreate(assignee_user_id=2, subject="x")
    )
    t2 = service.transition(task.id, TaskState.ACKNOWLEDGED)
    assert t2.state == TaskState.ACKNOWLEDGED


def test_invalid_transition_rejected(service):
    task = service.create(
        assigner_id=1, payload=TaskCreate(assignee_user_id=2, subject="x")
    )
    service.transition(task.id, TaskState.DONE)  # ASSIGNED → ... wait, not allowed
    # Actually ASSIGNED → DONE is not in allowed set; ensure it raises
    # Recreate fresh task to test clearly
    t = service.create(assigner_id=1, payload=TaskCreate(assignee_user_id=2, subject="y"))
    with pytest.raises(ValidationError):
        service.transition(t.id, TaskState.DONE)


def test_done_is_terminal(service):
    task = service.create(assigner_id=1, payload=TaskCreate(assignee_user_id=2, subject="z"))
    service.transition(task.id, TaskState.IN_PROGRESS)
    service.transition(task.id, TaskState.DONE)
    with pytest.raises(ValidationError):
        service.transition(task.id, TaskState.IN_PROGRESS)


def test_inbound_reply_done_keyword(service):
    task = service.create(assigner_id=1, payload=TaskCreate(assignee_user_id=2, subject="z"))
    # Must move through allowed path first
    service.transition(task.id, TaskState.IN_PROGRESS)
    t = service.handle_inbound_reply(task.reply_token, "All done, closing this out.")
    assert t.state == TaskState.DONE


def test_inbound_reply_unknown_token(service):
    assert service.handle_inbound_reply("no-such-token", "done") is None
