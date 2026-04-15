from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class AITask(str, Enum):
    SUMMARIZE_THREAD = "summarize_thread"
    DRAFT_REPLY = "draft_reply"
    DAILY_BRIEFING = "daily_briefing"


@dataclass
class SummarizeRequest:
    account_id: str
    user_id: str
    trace_id: str
    thread_id: str
    messages: list[dict]  # [{from, subject, body, received_at}]
    instructions: str = ""


@dataclass
class DraftReplyRequest:
    account_id: str
    user_id: str
    trace_id: str
    thread_id: str
    messages: list[dict]
    instructions: str = ""


@dataclass
class DailyBriefingRequest:
    account_id: str
    user_id: str
    trace_id: str
    urgent_mails: list[dict]    # summarized urgent mail info
    todays_meetings: list[dict]  # [{title, start, end, location}]
    pending_tasks: list[dict]   # [{subject, due_at, status}]


@dataclass
class AIResponse:
    task: AITask
    output: str                  # The generated text
    sources: list[dict]          # Retrieved chunks used
    model_id: str
    prompt_template_id: str
    retrieved_chunk_count: int
    duration_ms: float
    trace_id: str
