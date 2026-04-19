"""SQLAlchemy ORM models (PRD §5 data model).

Every account-scoped entity carries `owner_account_id` to enforce per-linked-account
isolation at the storage layer (PRD §8.2).
"""
from app.domain.models.audit import AuditEvent, ConsentRecord
from app.domain.models.contact import Contact, OutOfOffice, SignatureTemplate
from app.domain.models.mail import Attachment, MailMessage, UrgencyRule
from app.domain.models.meeting import Meeting, Resource, TimetableSlot
from app.domain.models.notification import NotificationEvent
from app.domain.models.task import Task
from app.domain.models.travel import TravelPlan
from app.domain.models.user import AppUser, LinkedAccount, RoleTemplate

__all__ = [
    "AppUser",
    "LinkedAccount",
    "RoleTemplate",
    "MailMessage",
    "Attachment",
    "UrgencyRule",
    "NotificationEvent",
    "Meeting",
    "Resource",
    "TimetableSlot",
    "Task",
    "TravelPlan",
    "Contact",
    "SignatureTemplate",
    "OutOfOffice",
    "AuditEvent",
    "ConsentRecord",
]
