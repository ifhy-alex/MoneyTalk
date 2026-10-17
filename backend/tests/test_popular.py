from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.ingestion import service
from moneytalk.ingestion.merchant import normalize_merchant
from moneytalk.ingestion.parsers import ParseError, find_statement_parser
from moneytalk.ingestion.parsers.popular import PopularStatementParser, dedupe_truncated
from moneytalk.ingestion.privacy import iban_bank_code, redact_document
from moneytalk.models import Account, AccountKind, RawDocument, SourceType
from tests.helpers import FIXTURES

TEXT = (FIXTURES / "statements" / "popular_movimientos.txt").read_text(encoding="utf-8")


def test_redaction_keeps_only_last4_and_bank_code() -> None:
    red = redact_document(TEXT)
    assert "12345678901" not in red and "CR05016100012345678901" not in red
    assert "CR** 0161 **** 8901" in red and iban_bank_code(red) == "161"
    assert "Cuenta:                                     ****8901" in red
    assert "PERSONA DE EJEMPLO" not in red and "<titular>" in red
    assert "88887777" not in red and "86665555" not in red  # teléfonos SINPE


def test_parser_reads_movements_and_validates_balance() -> None:
    red = redact_document(TEXT)
    assert isinstance(find_statement_parser(red), PopularStatementParser)
    txns = PopularStatementParser().parse(red)
    assert len(txns) == 7
    assert {t.last4 for t in txns} == {"8901"}
    assert all(t.account_kind is AccountKind.SAVINGS for t in txns)
    assert sum(t.amount for t in txns) == Decimal("91430.85") - Decimal("100000.00")
    by_merchant = {t.merchant: t.amount for t in txns}
    assert by_merchant["COMISION FS SUPERCELLSTORE fsprg nl"] == Decimal("-10.15")
    assert by_merchant["SODA EJEMPLO SAN JOSE CR"] == Decimal("-5250.00")
    assert by_merchant["CREDITO SINPE MOVIL"] == Decimal("15000.00")
    assert by_merchant["SINPE MOVIL comida"] == Decimal("-17181.69")
    assert by_merchant["Interes Credito"] == Decimal("49.15")
    assert txns[0].occurred_at is not None and txns[0].occurred_at.hour == 14


def test_balance_mismatch_is_detected() -> None:
    broken = redact_document(TEXT).replace("₡99,313.39", "₡99,000.00", 1)
    with pytest.raises(ParseError, match="saldo no cuadra"):
        PopularStatementParser().parse(broken)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("NOVA SAN JOSE CRNOVA SAN JOSE", "NOVA SAN JOSE CR"),
        ("FS SUPERCFS SUPERCELLSTORE fsprg nl", "FS SUPERCELLSTORE fsprg nl"),
        ("TACO BELL PARAISO CART CARTAGO", "TACO BELL PARAISO CART CARTAGO"),
    ],
)
def test_dedupe_truncated(raw: str, clean: str) -> None:
    assert dedupe_truncated(raw) == clean


def test_google_alias() -> None:
    assert normalize_merchant("G gle Castle Busters 650 253000").startswith("GOOGLE CASTLE")


def test_ingested_document_is_stored_redacted(db: Session) -> None:
    raw = service.store_raw(
        db, source_type=SourceType.PDF_STATEMENT, external_id="sha", content_text=TEXT
    )
    assert raw is not None
    result = service.process_raw(db, raw)
    assert result.transactions_created == 7
    stored = db.scalars(select(RawDocument)).one().content_text
    assert "12345678901" not in stored and "PERSONA DE EJEMPLO" not in stored
    acct = db.scalars(select(Account)).one()
    assert (acct.institution, acct.last4) == ("POPULAR", "8901")
