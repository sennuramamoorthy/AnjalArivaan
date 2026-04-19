"""Travel service tests — approval chain."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import ValidationError
from app.domain.models.travel import TravelStatus
from app.domain.schemas.travel import TravelPlanCreate
from app.repositories.travel import TravelPlanRepository
from app.services.travel_service import TravelService


@pytest.fixture
def svc(db):
    return TravelService(TravelPlanRepository(db))


def _payload():
    now = datetime.now(timezone.utc)
    return TravelPlanCreate(
        purpose="AICTE audit",
        destination="Delhi",
        start_date=now + timedelta(days=3),
        end_date=now + timedelta(days=5),
        approval_chain=[2, 3],
    )


def test_create_is_draft(svc):
    p = svc.create(1, _payload())
    assert p.status == TravelStatus.DRAFT


def test_submit_requires_approval_chain(svc):
    bad = _payload()
    bad.approval_chain = []
    p = svc.create(1, bad)
    with pytest.raises(ValidationError):
        svc.submit(p.id)


def test_submit_transitions_to_submitted(svc):
    p = svc.create(1, _payload())
    p2 = svc.submit(p.id)
    assert p2.status == TravelStatus.SUBMITTED


@pytest.mark.asyncio
async def test_wrong_approver_rejected(svc):
    p = svc.create(1, _payload())
    svc.submit(p.id)
    with pytest.raises(ValidationError):
        await svc.approve(p.id, approver_user_id=999)


@pytest.mark.asyncio
async def test_full_approval_chain(svc):
    p = svc.create(1, _payload())
    svc.submit(p.id)
    p = await svc.approve(p.id, approver_user_id=2)
    assert p.status == TravelStatus.IN_PROGRESS
    p = await svc.approve(p.id, approver_user_id=3)
    assert p.status == TravelStatus.APPROVED
