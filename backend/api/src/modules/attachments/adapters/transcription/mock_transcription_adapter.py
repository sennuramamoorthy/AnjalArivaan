"""MockTranscriptionAdapter — canned output for tests."""

from .interface import ITranscriptionAdapter, TranscriptionResult


class MockTranscriptionAdapter(ITranscriptionAdapter):
    def __init__(
        self,
        text: str = "mock transcription",
        language: str = "en",
        extractor: str = "mock-whisper",
    ) -> None:
        self._text = text
        self._language = language
        self._extractor = extractor
        self.calls: list[tuple[bytes, str]] = []

    async def transcribe(self, data: bytes, mime_type: str) -> TranscriptionResult:
        self.calls.append((data, mime_type))
        return TranscriptionResult(
            text=self._text,
            language=self._language,
            extractor=self._extractor,
        )
