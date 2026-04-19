"""AI DTOs."""
from pydantic import BaseModel


class SummarizeThreadRequest(BaseModel):
    thread_id: str


class DraftReplyRequest(BaseModel):
    mail_id: int
    tone: str = "formal"


class AIResponse(BaseModel):
    text: str
    citations: list[dict]
    model_id: str
    template_id: str
    latency_ms: int
    trace_id: str


class BriefingRequest(BaseModel):
    cadence_hour_ist: int = 6


class BriefingResponse(BaseModel):
    generated_at: str
    user_id: int
    account_id: int | None
    summary: str
    sections: dict
