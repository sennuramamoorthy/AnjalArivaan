"""FastAPI dependencies — wire repositories, services, and auth."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.domain.models.user import AppUser
from app.integrations.google.stub import StubGoogleCalendarClient, StubGoogleMailClient
from app.integrations.llm.factory import get_llm_client
from app.integrations.search import InMemorySearchClient
from app.integrations.storage import InMemoryObjectStorage
from app.integrations.vault.factory import get_secret_store
from app.integrations.vector import InMemoryVectorStore
from app.integrations.whatsapp.factory import get_whatsapp_client
from app.repositories.audit import AuditRepository, ConsentRepository
from app.repositories.contact import (
    ContactRepository,
    OutOfOfficeRepository,
    SignatureRepository,
)
from app.repositories.mail import (
    AttachmentRepository,
    MailMessageRepository,
    UrgencyRuleRepository,
)
from app.repositories.meeting import (
    MeetingRepository,
    ResourceRepository,
    TimetableRepository,
)
from app.repositories.notification import NotificationRepository
from app.repositories.task import TaskRepository
from app.repositories.travel import TravelPlanRepository
from app.repositories.user import (
    AppUserRepository,
    LinkedAccountRepository,
    RoleTemplateRepository,
)
from app.services.account_service import AccountService
from app.services.ai_service import AIService
from app.services.attachment_service import AttachmentService
from app.services.audit_service import AuditService, ConsentService
from app.services.auth_service import AuthService
from app.services.briefing_service import BriefingService
from app.services.contacts_service import (
    ContactsService,
    OutOfOfficeService,
    SignatureService,
)
from app.services.mail_service import MailService
from app.services.meeting_service import MeetingService
from app.services.resource_service import ResourceService
from app.services.search_service import SearchService
from app.services.task_service import TaskService
from app.services.timetable_service import TimetableService
from app.services.travel_service import TravelService
from app.services.urgent_service import UrgentNotificationService

# ---- Process-wide singletons for integrations (dev / stub wiring) ----------
_vector_store = InMemoryVectorStore()
_search_client = InMemorySearchClient()
_object_storage = InMemoryObjectStorage()
_google_mail = StubGoogleMailClient()
_google_calendar = StubGoogleCalendarClient()
_whatsapp = get_whatsapp_client()
_llm = get_llm_client()
_secret_store = get_secret_store()

DbDep = Annotated[Session, Depends(get_db)]


# ---- Repositories ----------------------------------------------------------

def _users(db: DbDep) -> AppUserRepository:
    return AppUserRepository(db)

def _linked(db: DbDep) -> LinkedAccountRepository:
    return LinkedAccountRepository(db)

def _roles(db: DbDep) -> RoleTemplateRepository:
    return RoleTemplateRepository(db)

def _mail(db: DbDep) -> MailMessageRepository:
    return MailMessageRepository(db)

def _att(db: DbDep) -> AttachmentRepository:
    return AttachmentRepository(db)

def _rules(db: DbDep) -> UrgencyRuleRepository:
    return UrgencyRuleRepository(db)

def _meeting(db: DbDep) -> MeetingRepository:
    return MeetingRepository(db)

def _resource(db: DbDep) -> ResourceRepository:
    return ResourceRepository(db)

def _tt(db: DbDep) -> TimetableRepository:
    return TimetableRepository(db)

def _task(db: DbDep) -> TaskRepository:
    return TaskRepository(db)

def _travel(db: DbDep) -> TravelPlanRepository:
    return TravelPlanRepository(db)

def _contact(db: DbDep) -> ContactRepository:
    return ContactRepository(db)

def _sig(db: DbDep) -> SignatureRepository:
    return SignatureRepository(db)

def _ooo(db: DbDep) -> OutOfOfficeRepository:
    return OutOfOfficeRepository(db)

def _notif(db: DbDep) -> NotificationRepository:
    return NotificationRepository(db)

def _audit_repo(db: DbDep) -> AuditRepository:
    return AuditRepository(db)

def _consent_repo(db: DbDep) -> ConsentRepository:
    return ConsentRepository(db)


# ---- Services --------------------------------------------------------------

def get_auth_service(users: AppUserRepository = Depends(_users)) -> AuthService:
    return AuthService(users)


def get_account_service(
    accounts: LinkedAccountRepository = Depends(_linked),
) -> AccountService:
    return AccountService(accounts, _secret_store)


def get_mail_service(repo: MailMessageRepository = Depends(_mail)) -> MailService:
    return MailService(repo)


def get_urgent_service(
    mail_repo: MailMessageRepository = Depends(_mail),
    rule_repo: UrgencyRuleRepository = Depends(_rules),
    users: AppUserRepository = Depends(_users),
    notifs: NotificationRepository = Depends(_notif),
) -> UrgentNotificationService:
    return UrgentNotificationService(
        mail_repo=mail_repo,
        rule_repo=rule_repo,
        users=users,
        notifications=notifs,
        whatsapp=_whatsapp,
    )


def get_ai_service(
    mail_repo: MailMessageRepository = Depends(_mail),
    users: AppUserRepository = Depends(_users),
    roles: RoleTemplateRepository = Depends(_roles),
) -> AIService:
    return AIService(
        llm=_llm, mail_repo=mail_repo, users=users, roles=roles, vector=_vector_store
    )


def get_meeting_service(
    meetings: MeetingRepository = Depends(_meeting),
    resources: ResourceRepository = Depends(_resource),
    timetable: TimetableRepository = Depends(_tt),
) -> MeetingService:
    return MeetingService(
        meetings=meetings, resources=resources, timetable=timetable, calendar=_google_calendar
    )


def get_resource_service(repo: ResourceRepository = Depends(_resource)) -> ResourceService:
    return ResourceService(repo)


def get_timetable_service(repo: TimetableRepository = Depends(_tt)) -> TimetableService:
    return TimetableService(repo)


def get_task_service(repo: TaskRepository = Depends(_task)) -> TaskService:
    return TaskService(repo)


def get_travel_service(repo: TravelPlanRepository = Depends(_travel)) -> TravelService:
    return TravelService(repo, _google_calendar)


def get_contacts_service(repo: ContactRepository = Depends(_contact)) -> ContactsService:
    return ContactsService(repo)


def get_signature_service(repo: SignatureRepository = Depends(_sig)) -> SignatureService:
    return SignatureService(repo, _google_mail)


def get_ooo_service(repo: OutOfOfficeRepository = Depends(_ooo)) -> OutOfOfficeService:
    return OutOfOfficeService(repo, _google_mail)


def get_briefing_service(
    mail_repo: MailMessageRepository = Depends(_mail),
    meetings: MeetingRepository = Depends(_meeting),
    tasks: TaskRepository = Depends(_task),
    travel: TravelPlanRepository = Depends(_travel),
    users: AppUserRepository = Depends(_users),
) -> BriefingService:
    return BriefingService(
        llm=_llm,
        mail_repo=mail_repo,
        meetings=meetings,
        tasks=tasks,
        travel=travel,
        users=users,
    )


def get_search_service() -> SearchService:
    return SearchService(_search_client, _vector_store)


def get_attachment_service(
    att: AttachmentRepository = Depends(_att),
) -> AttachmentService:
    return AttachmentService(
        repo=att, storage=_object_storage, vector=_vector_store
    )


def get_audit_service(repo: AuditRepository = Depends(_audit_repo)) -> AuditService:
    return AuditService(repo)


def get_consent_service(repo: ConsentRepository = Depends(_consent_repo)) -> ConsentService:
    return ConsentService(repo)


# ---- Current user ----------------------------------------------------------

def current_user(
    authorization: Annotated[str | None, Header()] = None,
    users: AppUserRepository = Depends(_users),
) -> AppUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    user = users.get(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[AppUser, Depends(current_user)]


def require_super_admin(user: CurrentUser) -> AppUser:
    if not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="super_admin required")
    return user
