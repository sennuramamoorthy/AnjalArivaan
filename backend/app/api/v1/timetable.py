"""Timetable endpoints."""
from fastapi import APIRouter, Depends, status

from app.api.deps import get_timetable_service, require_super_admin
from app.domain.schemas.meeting import TimetableSlotCreate, TimetableSlotOut
from app.services.timetable_service import TimetableService

router = APIRouter()


@router.post(
    "",
    response_model=TimetableSlotOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin)],
)
def create_slot(
    payload: TimetableSlotCreate, svc: TimetableService = Depends(get_timetable_service)
):
    return TimetableSlotOut.model_validate(svc.create_slot(payload))


@router.get("/classroom/{classroom_id}", response_model=list[TimetableSlotOut])
def list_for_classroom(
    classroom_id: int, term: str, svc: TimetableService = Depends(get_timetable_service)
):
    return [TimetableSlotOut.model_validate(s) for s in svc.list_for_classroom(classroom_id, term)]
