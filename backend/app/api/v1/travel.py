"""Travel."""
from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_travel_service
from app.domain.schemas.travel import TravelPlanCreate, TravelPlanOut
from app.services.travel_service import TravelService

router = APIRouter()


@router.post("", response_model=TravelPlanOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: TravelPlanCreate,
    user: CurrentUser,
    svc: TravelService = Depends(get_travel_service),
):
    return TravelPlanOut.model_validate(svc.create(user.id, payload))


@router.get("", response_model=list[TravelPlanOut])
def list_mine(user: CurrentUser, svc: TravelService = Depends(get_travel_service)):
    return [TravelPlanOut.model_validate(p) for p in svc.list_for_user(user.id)]


@router.post("/{plan_id}/submit", response_model=TravelPlanOut)
def submit(plan_id: int, svc: TravelService = Depends(get_travel_service)):
    return TravelPlanOut.model_validate(svc.submit(plan_id))


@router.post("/{plan_id}/approve", response_model=TravelPlanOut)
async def approve(
    plan_id: int,
    user: CurrentUser,
    svc: TravelService = Depends(get_travel_service),
):
    return TravelPlanOut.model_validate(await svc.approve(plan_id, user.id))


@router.post("/{plan_id}/reject", response_model=TravelPlanOut)
def reject(plan_id: int, svc: TravelService = Depends(get_travel_service)):
    return TravelPlanOut.model_validate(svc.reject(plan_id))
