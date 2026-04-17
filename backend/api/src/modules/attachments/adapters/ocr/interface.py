"""IOcrAdapter — extract text from PDFs / images.

Implementations:
  - TesseractAdapter (English, local)
  - IndicOcrAdapter (Tamil, stubbed — real service runs on GPU node)
  - MockOcrAdapter (tests)

Returns a (text, language) tuple. Callers log ``char_count`` and
``language`` but MUST NOT log ``text`` itself (may contain sensitive
gov/PII content — see CLAUDE.md security rules).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OcrResult:
    text: str
    language: str  # ISO 639-1 — "en", "ta", ...
    extractor: str  # "tesseract", "indic-ocr", ...


class IOcrAdapter(ABC):
    @abstractmethod
    async def extract(self, data: bytes, mime_type: str) -> OcrResult:
        ...
