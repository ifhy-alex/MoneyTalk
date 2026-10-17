from datetime import date
from decimal import Decimal

import pytest

from moneytalk.ingestion.merchant import merchant_similarity, normalize_merchant
from moneytalk.ingestion.parsers import ParseError, find_email_parser, find_statement_parser
from moneytalk.ingestion.parsers.bac import BacEmailParser, BacStatementParser
from moneytalk.ingestion.parsers.bn import BnEmailParser
from moneytalk.ingestion.pdf import pdf_to_text
from moneytalk.ingestion.text import parse_amount
from moneytalk.ingestion.types import EmailMessage
from moneytalk.models import AccountKind
from tests.helpers import FIXTURES, email_fixture, statement_pdf

BAC_SENDER = "Notificacion BAC <notificacion@notificacionesbaccr.com>"
BN_SENDER = "BN Notificaciones <notificaciones@bncr.fi.cr>"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("15,250.50", Decimal("15250.50")),
        ("15.250,50", Decimal("15250.50")),
        ("₡15 250,50", Decimal("15250.50")),
        ("-100,000.00", Decimal("-100000.00")),
        ("12.99", Decimal("12.99")),
        ("1,000", Decimal("1000")),
    ],
)
def test_parse_amount(raw: str, expected: Decimal) -> None:
    assert parse_amount(raw) == expected


def test_bac_email_purchase() -> None:
    msg = email_fixture("bac_compra.html", BAC_SENDER)
    assert isinstance(find_email_parser(msg), BacEmailParser)
    [txn] = BacEmailParser().parse(msg)
    assert txn.last4 == "4821"
    assert txn.amount == Decimal("-15250.50")
    assert txn.currency == "CRC"
    assert txn.merchant == "AUTO MERCADO ESCAZU"
    assert txn.txn_date == date(2026, 10, 16)
    assert txn.occurred_at is not None and txn.occurred_at.hour == 14
    assert txn.reference == "000123"
    assert txn.account_kind is AccountKind.CREDIT_CARD


def test_bac_email_refund_is_positive() -> None:
    [txn] = BacEmailParser().parse(email_fixture("bac_devolucion.html", BAC_SENDER))
    assert txn.amount == Decimal("45.99")
    assert txn.currency == "USD"
    assert txn.last4 == "9937"


def test_bac_email_non_transaction_returns_empty() -> None:
    msg = EmailMessage("x", BAC_SENDER, "Promoción", None, "Aproveche 0% de interés")
    assert BacEmailParser().parse(msg) == []


def test_bac_email_without_card_raises() -> None:
    msg = EmailMessage("x", BAC_SENDER, "s", None, "Comercio: X\nMonto: CRC 100.00")
    with pytest.raises(ParseError):
        BacEmailParser().parse(msg)


def test_bn_email_purchase() -> None:
    msg = email_fixture("bn_compra.txt", BN_SENDER)
    assert isinstance(find_email_parser(msg), BnEmailParser)
    [txn] = BnEmailParser().parse(msg)
    assert txn.institution == "BN"
    assert txn.account_kind is AccountKind.DEBIT_CARD
    assert txn.last4 == "5678"
    assert txn.amount == Decimal("-12.99")
    assert txn.currency == "USD"
    assert txn.merchant == "NETFLIX.COM"


def test_unknown_sender_has_no_parser() -> None:
    assert find_email_parser(EmailMessage("x", "otro@banco.com", "", None, "")) is None


def test_bac_statement_from_text() -> None:
    text = (FIXTURES / "statements" / "bac_tarjeta.txt").read_text(encoding="utf-8")
    assert isinstance(find_statement_parser(text), BacStatementParser)
    txns = BacStatementParser().parse(text)
    assert [t.amount for t in txns] == [
        Decimal("100000.00"),
        Decimal("-8.40"),
        Decimal("-15250.50"),
        Decimal("-5.99"),
    ]
    assert {t.last4 for t in txns} == {"4821"}
    assert len({t.line_no for t in txns}) == 4


def test_bac_statement_from_real_pdf_roundtrip() -> None:
    text = pdf_to_text(statement_pdf())
    assert len(BacStatementParser().parse(text)) == 4


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("AUTO MERCADO ESCAZU SAN JOSE CR", "AUTO MERCADO ESCAZU"),
        ("PAYPAL *SPOTIFY", "SPOTIFY"),
        ("NETFLIX.COM", "NETFLIX"),
        ("UBER TRIP 8823 HELP.UBER.COM", "UBER TRIP HELP UBER"),
    ],
)
def test_normalize_merchant(raw: str, normalized: str) -> None:
    assert normalize_merchant(raw) == normalized


def test_merchant_similarity_variants() -> None:
    assert merchant_similarity("AUTO MERCADO ESCAZU", "AUTOMERCADO ESCAZU") > 0.9
    assert merchant_similarity("NETFLIX.COM", "UBER TRIP") < 0.5
