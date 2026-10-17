from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.db import get_db
from moneytalk.models import Account, AccountKind

router = APIRouter(prefix="/accounts", tags=["cuentas"])
DB = Annotated[Session, Depends(get_db)]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    institution: str
    kind: AccountKind
    last4: str
    currency: str
    nickname: str | None
    is_active: bool


class AccountPatch(BaseModel):
    nickname: str | None = None
    is_active: bool | None = None


@router.get("", response_model=list[AccountOut])
def list_accounts(db: DB) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.institution, Account.last4)))


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(db: DB, account_id: int, patch: AccountPatch) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="cuenta no encontrada")
    for key, value in patch.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.commit()
    return account
