"""v1 API router aggregator."""
from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    admin,
    ai,
    audit,
    auth,
    briefing,
    contacts,
    mail,
    meetings,
    resources,
    search,
    tasks,
    timetable,
    travel,
    urgent,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(mail.router, prefix="/mail", tags=["mail"])
api_router.include_router(urgent.router, prefix="/urgent", tags=["urgent"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(travel.router, prefix="/travel", tags=["travel"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(briefing.router, prefix="/briefing", tags=["briefing"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
