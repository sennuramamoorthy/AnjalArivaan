import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.modules.ai.domain.task import SummarizeRequest

router = APIRouter()


class SummarizeHttpRequest(BaseModel):
    account_id: str
    user_id: str
    thread_id: str
    messages: list[dict]
    instructions: str = ""


@router.post("/summarize")
async def summarize_thread(body: SummarizeHttpRequest, request: Request) -> dict:
    orchestrator = request.app.state.orchestrator
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    req = SummarizeRequest(trace_id=trace_id, **body.model_dump())
    response = await orchestrator.summarize(req)
    return {
        "success": True,
        "data": {
            "summary": response.output,
            "sources": response.sources,
            "model_id": response.model_id,
            "prompt_template_id": response.prompt_template_id,
            "retrieved_chunk_count": response.retrieved_chunk_count,
        },
        "meta": {"trace_id": trace_id, "duration_ms": response.duration_ms},
    }
