from dataclasses import dataclass, field


@dataclass
class Attachment:
    id: str
    mail_id: str
    filename: str
    mime_type: str
    size_bytes: int
    gmail_attachment_id: str   # for fetching from Gmail API
    minio_key: str = ""        # set after upload
