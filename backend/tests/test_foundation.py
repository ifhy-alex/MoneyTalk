from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moneytalk.log import redact
from moneytalk.models import (
    Account,
    AccountKind,
    RawDocument,
    SourceType,
    Transaction,
    TransactionSource,
)


def _account(**kw: object) -> Account:
    data: dict[str, object] = {
        "institution": "BAC",
        "kind": AccountKind.CREDIT_CARD,
        "last4": "1234",
        "currency": "CRC",
    }
    data.update(kw)
    return Account(**data)


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_last4_rejects_full_card_numbers(db: Session) -> None:
    db.add(_account(last4="12AB"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_raw_document_unique_hash(db: Session) -> None:
    for ext in ("m1", "m2"):
        db.add(
            RawDocument(
                source_type=SourceType.EMAIL,
                external_id=ext,
                content_text="mismo texto",
                content_hash="a" * 64,
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


def test_transaction_with_multiple_sources(db: Session) -> None:
    acct = _account()
    email = RawDocument(
        source_type=SourceType.EMAIL, external_id="m1", content_text="x", content_hash="b" * 64
    )
    pdf = RawDocument(
        source_type=SourceType.PDF_STATEMENT,
        external_id="sha",
        content_text="y",
        content_hash="c" * 64,
    )
    txn = Transaction(
        account=acct,
        txn_date=date(2026, 10, 1),
        amount=Decimal("-15250.50"),
        currency="CRC",
        merchant_raw="AUTO MERCADO ESCAZU",
        merchant_normalized="AUTO MERCADO",
        sources=[
            TransactionSource(raw_document=email, extracted={"a": 1}),
            TransactionSource(raw_document=pdf, line_no=3, extracted={"b": 2}),
        ],
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)
    assert len(txn.sources) == 2
    assert txn.amount == Decimal("-15250.50")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tarjeta 4111 1111 1111 1111 aprobada", "Tarjeta **** aprobada"),
        ("Cuenta CR05015202001026284066", "Cuenta CR**IBAN**"),
        ("Escribir a juan.perez@correo.com", "Escribir a <email>"),
        ("Monto 15,250.50 en 1234", "Monto 15,250.50 en 1234"),
    ],
)
def test_redact(raw: str, expected: str) -> None:
    assert redact(raw) == expected
