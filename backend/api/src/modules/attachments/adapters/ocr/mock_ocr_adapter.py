"""MockOcrAdapter — returns canned text; for unit tests."""

from .interface import IOcrAdapter, OcrResult


class MockOcrAdapter(IOcrAdapter):
    def __init__(
        self,
        text: str = "mock ocr text",
        language: str = "en",
        extractor: str = "mock-ocr",
    ) -> None:
        self._text = text
        self._language = language
        self._extractor = extractor
        self.calls: list[tuple[bytes, str]] = []

    async def extract(self, data: bytes, mime_type: str) -> OcrResult:
        self.calls.append((data, mime_type))
        return OcrResult(
            text=self._text,
            language=self._language,
            extractor=self._extractor,
        )
