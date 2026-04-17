"""IAttachmentExtractionRepository — persistence boundary."""

from abc import ABC, abstractmethod

from ..domain.extraction import AttachmentExtraction


class IAttachmentExtractionRepository(ABC):
    @abstractmethod
    async def save(self, extraction: AttachmentExtraction) -> None:
        """Persist extraction. MUST encrypt ``extracted_text`` at rest."""
        ...

    @abstractmethod
    async def find_by_attachment_id(
        self, attachment_id: str
    ) -> AttachmentExtraction | None:
        ...
