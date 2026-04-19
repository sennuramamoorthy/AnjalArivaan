"""Contacts, signature, out-of-office endpoints."""
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUser,
    get_account_service,
    get_contacts_service,
    get_ooo_service,
    get_signature_service,
)
from app.domain.schemas.contact import (
    ContactCreate,
    ContactOut,
    OutOfOfficeCreate,
    OutOfOfficeOut,
    SignatureCreate,
    SignatureOut,
)
from app.services.account_service import AccountService
from app.services.contacts_service import (
    ContactsService,
    OutOfOfficeService,
    SignatureService,
)

router = APIRouter()


@router.get("", response_model=list[ContactOut])
def list_contacts(
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: ContactsService = Depends(get_contacts_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return [ContactOut.model_validate(c) for c in svc.list(account_id)]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: ContactsService = Depends(get_contacts_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return ContactOut.model_validate(svc.create(account_id, payload))


@router.post("/signature", response_model=SignatureOut, status_code=status.HTTP_201_CREATED)
def create_signature(
    payload: SignatureCreate,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: SignatureService = Depends(get_signature_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return SignatureOut.model_validate(svc.create(account_id, payload))


@router.post("/signature/{signature_id}/default", response_model=SignatureOut)
async def set_default_signature(
    signature_id: int,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: SignatureService = Depends(get_signature_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return SignatureOut.model_validate(await svc.set_default(account_id, signature_id))


@router.post("/ooo", response_model=OutOfOfficeOut, status_code=status.HTTP_201_CREATED)
async def set_ooo(
    payload: OutOfOfficeCreate,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: OutOfOfficeService = Depends(get_ooo_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return OutOfOfficeOut.model_validate(await svc.set_ooo(account_id, payload))
