from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from moneytalk.db import get_db
from moneytalk.models import CategorySource, CategoryStatus, SourceType, Transaction

router = APIRouter(prefix="/transactions", tags=["transacciones"])
DB = Annotated[Session, Depends(get_db)]


class SourceOut(BaseModel):
    raw_document_id: int
    source_type: SourceType
    match_confidence: Decimal


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_label: str
    txn_date: date
    occurred_at: datetime | None
    amount: Decimal
    currency: str
    merchant_raw: str
    merchant_normalized: str
    category_id: int | None
    category_name: str | None
    category_status: CategoryStatus
    category_source: CategorySource | None
    ai_reason: str | None
    notes: str | None
    sources: list[SourceOut]


def to_out(txn: Transaction) -> TransactionOut:
    acct = txn.account
    return TransactionOut(
        id=txn.id,
        account_id=txn.account_id,
        account_label=acct.nickname or f"{acct.institution} ··{acct.last4}",
        txn_date=txn.txn_date,
        occurred_at=txn.occurred_at,
        amount=txn.amount,
        currency=txn.currency,
        merchant_raw=txn.merchant_raw,
        merchant_normalized=txn.merchant_normalized,
        category_id=txn.category_id,
        category_name=txn.category.name if txn.category else None,
        category_status=txn.category_status,
        category_source=txn.category_source,
        ai_reason=txn.ai_reason,
        notes=txn.notes,
        sources=[
            SourceOut(
                raw_document_id=s.raw_document_id,
                source_type=s.raw_document.source_type,
                match_confidence=s.match_confidence,
            )
            for s in txn.sources
        ],
    )


def load(db: Session, txn_id: int) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transacción no encontrada")
    return txn


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    db: DB,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    status: CategoryStatus | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(le=1000)] = 200,
    offset: int = 0,
) -> list[TransactionOut]:
    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.account),
            selectinload(Transaction.category),
            selectinload(Transaction.sources),
        )
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if month:
        year, mon = (int(x) for x in month.split("-"))
        stmt = stmt.where(
            extract("year", Transaction.txn_date) == year,
            extract("month", Transaction.txn_date) == mon,
        )
    if status:
        stmt = stmt.where(Transaction.category_status == status)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if q:
        stmt = stmt.where(Transaction.merchant_normalized.ilike(f"%{q.upper()}%"))
    return [to_out(t) for t in db.scalars(stmt)]


@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(db: DB, txn_id: int) -> TransactionOut:
    return to_out(load(db, txn_id))
