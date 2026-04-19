"""Attachment pipeline: virus scan, extraction, chunk, embed, index."""
import pytest

from app.domain.models.mail import AttachmentStatus
from app.integrations.storage import InMemoryObjectStorage
from app.integrations.vector import InMemoryVectorStore
from app.repositories.mail import AttachmentRepository
from app.services.attachment_service import AttachmentService


@pytest.fixture
def svc(db):
    return AttachmentService(
        repo=AttachmentRepository(db),
        storage=InMemoryObjectStorage(),
        vector=InMemoryVectorStore(),
    )


@pytest.mark.asyncio
async def test_clean_file_reaches_indexed(svc):
    att = await svc.ingest(
        account_id=1,
        mail_id=1,
        filename="letter.txt",
        mime="text/plain",
        data=b"Hello, this is a real letter from UGC with content.",
    )
    assert att.status == AttachmentStatus.INDEXED
    assert att.extracted_text


@pytest.mark.asyncio
async def test_infected_file_quarantined(svc):
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    att = await svc.ingest(
        account_id=1,
        mail_id=1,
        filename="bad.com",
        mime="application/octet-stream",
        data=eicar,
    )
    assert att.status == AttachmentStatus.INFECTED
