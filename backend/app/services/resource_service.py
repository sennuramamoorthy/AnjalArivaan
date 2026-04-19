"""Resource / room catalog CRUD (PRD §3.6)."""
from app.domain.models.meeting import Resource
from app.domain.schemas.meeting import ResourceCreate
from app.repositories.meeting import ResourceRepository


class ResourceService:
    def __init__(self, repo: ResourceRepository) -> None:
        self.repo = repo

    def create(self, payload: ResourceCreate) -> Resource:
        r = Resource(**payload.model_dump())
        self.repo.add(r)
        self.repo.commit()
        return r

    def list(self, resource_type: str | None = None) -> list[Resource]:
        return self.repo.list_active(resource_type)

    def deactivate(self, resource_id: int) -> Resource:
        r = self.repo.get_or_404(resource_id)
        r.active = False
        self.repo.commit()
        return r
