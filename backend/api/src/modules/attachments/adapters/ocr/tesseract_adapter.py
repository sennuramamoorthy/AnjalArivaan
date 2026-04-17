"""TesseractAdapter — English OCR for PDFs and images via pytesseract.

Real import of ``pytesseract`` / ``pdf2image`` is deferred to ``extract``
so test environments without Tesseract binaries don't fail at import
time. Per CLAUDE.md D22, Phase 1a UI/AI output is English-only; this
adapter therefore only runs eng traineddata.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from .interface import IOcrAdapter, OcrResult


class TesseractAdapter(IOcrAdapter):
    def __init__(self, logger: Any) -> None:
        self._logger = logger

    async def extract(self, data: bytes, mime_type: str) -> OcrResult:
        loop = asyncio.get_event_loop()
        with self._logger.timed(
            "tesseract.extract", mime=mime_type, size_bytes=len(data)
        ):
            text = await loop.run_in_executor(
                None, self._extract_sync, data, mime_type
            )
        return OcrResult(text=text, language="en", extractor="tesseract")

    def _extract_sync(self, data: bytes, mime_type: str) -> str:
        import pytesseract  # type: ignore[import]
        from PIL import Image  # type: ignore[import]

        if mime_type == "application/pdf":
            from pdf2image import convert_from_bytes  # type: ignore[import]

            pages = convert_from_bytes(data)
            return "\n\n".join(
                pytesseract.image_to_string(p, lang="eng") for p in pages
            )
        image = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(image, lang="eng")
