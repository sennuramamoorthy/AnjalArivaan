from dataclasses import dataclass, field
from src.modules.ai.domain.task import AITask


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    source_mail_id: str | None = None


@dataclass
class AssembledContext:
    account_id: str
    user_id: str
    role_template: dict            # {designation, persona_prompt, kpis}
    primary_content: str           # The main text to process (thread, meetings, etc.)
    retrieved_chunks: list[RetrievedChunk]
    task: AITask
    instructions: str = ""
