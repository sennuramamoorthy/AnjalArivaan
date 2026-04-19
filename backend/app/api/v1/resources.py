"""Resource / room catalog endpoints."""
from fastapi import APIRouter, Depends, status

from app.api.deps import get_resource_service, require_super_admin
from app.domain.schemas.meeting import ResourceCreate, ResourceOut
from app.services.resource_service import ResourceService

router = APIRouter()


@router.get("", response_model=list[ResourceOut])
def list_resources(
    type: str | None = None, svc: ResourceService = Depends(get_resource_service)
):
    return [ResourceOut.model_validate(r) for r in svc.list(type)]


@router.post(
    "",
    response_model=ResourceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin)],
)
def create_resource(
    payload: ResourceCreate, svc: ResourceService = Depends(get_resource_service)
):
    return ResourceOut.model_validate(svc.create(payload))
