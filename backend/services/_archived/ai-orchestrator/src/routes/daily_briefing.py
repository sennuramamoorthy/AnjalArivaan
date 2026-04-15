import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.domain.task import DailyBriefingRequest

router = APIRouter()


class DailyBriefingHttpRequest(BaseModel):
    account_id: str
    user_id: str
    urgent_mails: list[dict] = []
    todays_meetings: list[dict] = []
    pending_tasks: list[dict] = []


@router.post("/daily-briefing")
async def daily_briefing(body: DailyBriefingHttpRequest, request: Request) -> dict:
    orchestrator = request.app.state.orchestrator
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    req = DailyBriefingRequest(trace_id=trace_id, **body.model_dump())
    response = await orchestrator.daily_briefing(req)
    return {
        "success": True,
        "data": {
            "briefing": response.output,
            "sources": response.sources,
            "model_id": response.model_id,
            "prompt_template_id": response.prompt_template_id,
            "retrieved_chunk_count": response.retrieved_chunk_count,
        },
        "meta": {"trace_id": trace_id, "duration_ms": response.duration_ms},
    }
