"""Travel plan repository."""
from sqlalchemy import select

from app.domain.models.travel import TravelPlan
from app.repositories.base import BaseRepository


class TravelPlanRepository(BaseRepository[TravelPlan]):
    model = TravelPlan

    def list_for_user(self, user_id: int) -> list[TravelPlan]:
        stmt = (
            select(TravelPlan)
            .where(TravelPlan.traveller_user_id == user_id)
            .order_by(TravelPlan.start_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
