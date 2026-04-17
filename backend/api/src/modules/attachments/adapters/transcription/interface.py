"""ITranscriptionAdapter — audio → text."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    text: str
    language: str
    extractor: str


class ITranscriptionAdapter(ABC):
    @abstractmethod
    async def transcribe(self, data: bytes, mime_type: str) -> TranscriptionResult:
        ...
