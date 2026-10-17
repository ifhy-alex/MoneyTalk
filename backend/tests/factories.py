"""Constructores de datos de prueba (todos ficticios)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.ingestion.merchant import normalize_merchant
from moneytalk.models import (
    Account,
    AccountKind,
    Category,
    CategoryStatus,
    ExchangeRate,
    Transaction,
)


def account(db: Session, last4: str = "4821") -> Account:
    acct = db.scalar(select(Account).where(Account.last4 == last4))
    if acct is None:
        acct = Account(institution="BAC", kind=AccountKind.CREDIT_CARD, last4=last4, currency="CRC")
        db.add(acct)
        db.flush()
    return acct


def category(db: Session, name: str) -> Category:
    return db.scalars(select(Category).where(Category.name == name)).one()


def txn(
    db: Session,
    day: date,
    amount: str | Decimal,
    merchant: str = "COMERCIO X",
    currency: str = "CRC",
    category_name: str | None = None,
) -> Transaction:
    t = Transaction(
        account=account(db),
        txn_date=day,
        amount=Decimal(amount),
        currency=currency,
        merchant_raw=merchant,
        merchant_normalized=normalize_merchant(merchant),
        category=category(db, category_name) if category_name else None,
        category_status=CategoryStatus.CONFIRMED if category_name else CategoryStatus.UNCATEGORIZED,
    )
    db.add(t)
    db.flush()
    return t


def rate(db: Session, day: date, sell: str = "510.00", buy: str = "503.00") -> ExchangeRate:
    r = ExchangeRate(rate_date=day, buy=Decimal(buy), sell=Decimal(sell))
    db.add(r)
    db.flush()
    return r
