"""Urgency rule management + manual evaluation endpoint."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, _mail, _rules, get_urgent_service, require_super_admin
from app.domain.models.mail import UrgencyRule
from app.domain.schemas.mail import UrgencyRuleCreate, UrgencyRuleOut
from app.repositories.mail import MailMessageRepository, UrgencyRuleRepository
from app.services.urgent_service import UrgentNotificationService

router = APIRouter()


@router.get("/rules", response_model=list[UrgencyRuleOut])
def list_rules(role: str, repo: UrgencyRuleRepository = Depends(_rules)):
    return [UrgencyRuleOut.model_validate(r) for r in repo.list_for_role(role)]


@router.post(
    "/rules",
    response_model=UrgencyRuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin)],
)
def create_rule(
    payload: UrgencyRuleCreate,
    admin: CurrentUser,
    repo: UrgencyRuleRepository = Depends(_rules),
):
    rule = UrgencyRule(**payload.model_dump(), created_by=admin.id)
    repo.add(rule)
    repo.commit()
    return UrgencyRuleOut.model_validate(rule)


@router.post("/evaluate/{mail_id}")
async def evaluate(
    mail_id: int,
    user: CurrentUser,
    mail_repo: MailMessageRepository = Depends(_mail),
    svc: UrgentNotificationService = Depends(get_urgent_service),
):
    mail = mail_repo.get(mail_id)
    if not mail:
        raise HTTPException(status_code=404, detail="mail not found")
    decision = await svc.evaluate_and_dispatch(mail, user)
    return {
        "matched": decision.matched,
        "rule_id": decision.rule_id,
        "deadline": decision.deadline,
        "reason": decision.reason,
    }
