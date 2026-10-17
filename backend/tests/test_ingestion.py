from collections.abc import Iterator
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.ingestion import service
from moneytalk.ingestion.types import EmailMessage
from moneytalk.models import Account, RawDocument, RawDocumentStatus, Transaction
from moneytalk.pipeline import ingest_gmail
from tests.helpers import email_fixture, statement_pdf, text_to_pdf

BAC_SENDER = "notificacion@notificacionesbaccr.com"


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_email_then_statement_deduplicates(db: Session) -> None:
    r1 = service.ingest_email(db, email_fixture("bac_compra.html", BAC_SENDER))
    assert r1.transactions_created == 1

    r2 = service.ingest_pdf(db, statement_pdf(), "octubre.pdf")
    # 4 líneas en el estado: 1 coincide con el correo (fecha +1 día, nombre distinto)
    assert r2.transactions_created == 3
    assert r2.transactions_merged == 1

    txn = db.scalars(select(Transaction).where(Transaction.amount == Decimal("-15250.50"))).one()
    assert len(txn.sources) == 2
    assert txn.occurred_at is not None  # se conserva la hora del correo
    assert txn.txn_date == date(2026, 10, 16)
    assert _count(db, Account) == 1


def test_same_email_twice_is_skipped(db: Session) -> None:
    msg = email_fixture("bac_compra.html", BAC_SENDER)
    service.ingest_email(db, msg)
    again = service.ingest_email(db, msg)
    assert again.documents_skipped == 1
    assert _count(db, Transaction) == 1


def test_two_identical_purchases_by_email_are_not_merged(db: Session) -> None:
    """Dos cafés iguales el mismo día por correo = dos transacciones reales."""
    base = email_fixture("bac_compra.html", BAC_SENDER)
    service.ingest_email(db, base)
    second = EmailMessage(
        message_id="otro-id",
        sender=base.sender,
        subject=base.subject,
        received_at=base.received_at,
        body_text=base.body_text.replace("000123", "000124"),
    )
    service.ingest_email(db, second)
    assert _count(db, Transaction) == 2


def test_unparseable_document_is_marked_failed(db: Session) -> None:
    msg = EmailMessage("bad", BAC_SENDER, "s", None, "Comercio: X\nMonto: CRC 100.00")
    result = service.ingest_email(db, msg)
    assert result.documents_failed == 1
    raw = db.scalars(select(RawDocument)).one()
    assert raw.status is RawDocumentStatus.FAILED
    assert raw.content_text  # el texto crudo se conserva para reprocesar


def test_reprocess_rebuilds_transactions(db: Session) -> None:
    service.ingest_pdf(db, statement_pdf())
    raw = db.scalars(select(RawDocument)).one()
    result = service.reprocess(db, raw)
    assert result.transactions_created == 4
    assert _count(db, Transaction) == 4


def test_statement_without_lines_fails(db: Session) -> None:
    data = text_to_pdf("BAC CREDOMATIC\nESTADO DE CUENTA\nTarjeta: XXXX-1111\nSin movimientos")
    result = service.ingest_pdf(db, data)
    assert result.documents_failed == 1


class FakeMail:
    def __init__(self, messages: list[EmailMessage]) -> None:
        self.messages = messages
        self.queries: list[str] = []

    def fetch(self, query: str) -> Iterator[EmailMessage]:
        self.queries.append(query)
        yield from self.messages


def test_ingest_gmail_filters_cr_banks_and_overlaps(db: Session) -> None:
    fake = FakeMail([email_fixture("bac_compra.html", BAC_SENDER)])
    settings = Settings(gmail_label="", gmail_extra_senders="mibanco.example")
    ingest_gmail(db, settings, source=fake)
    ingest_gmail(db, settings, source=fake)
    first, second = fake.queries
    assert first.startswith("from:(") and "bncr.fi.cr" in first and "mibanco.example" in first
    assert "after:" in first  # primera vez: últimos N días, no todo el historial
    assert second.endswith("after:2026/10/15")  # último correo (16/10) - 1 día
    assert _count(db, Transaction) == 1


def test_ingest_gmail_with_label() -> None:
    from moneytalk.ingestion.gmail import build_query

    assert build_query("Finanzas/Bancos", [], None) == "label:finanzas-bancos"


def test_upload_pdf_endpoint(client: TestClient) -> None:
    resp = client.post(
        "/api/ingestion/pdf", files={"file": ("estado.pdf", statement_pdf(), "application/pdf")}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["transactions_created"] == 4

    docs = client.get("/api/ingestion/documents").json()
    assert docs[0]["status"] == "parsed"
    assert "content_text" not in docs[0]

    txns = client.get("/api/transactions", params={"month": "2026-10"}).json()
    assert len(txns) == 4
    assert txns[0]["account_label"] == "BAC ··4821"
