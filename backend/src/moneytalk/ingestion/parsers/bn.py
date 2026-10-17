"""Banco Nacional: notificaciones de compra con tarjeta (texto en una sola oración)."""

import re

from moneytalk.ingestion.parsers.base import EmailParser, ParseError
from moneytalk.ingestion.parsers.common import parse_cr_datetime
from moneytalk.ingestion.text import normalize_currency, parse_amount, strip_accents
from moneytalk.ingestion.types import EmailMessage, ParsedTransaction
from moneytalk.models.accounts import AccountKind

_SENTENCE = re.compile(
    r"compra en (?P<merchant>.+?) por (?:un monto de )?(?P<cur>USD|CRC|US\$|₡|\$)\s?"
    r"(?P<amount>[\d.,]+?)\.?\s+con su tarjeta de (?P<kind>debito|credito) terminada en "
    r"(?P<last4>\d{4}) el (?P<date>\d{2}/\d{2}/\d{4})(?: a las (?P<time>\d{1,2}:\d{2}))?",
    re.IGNORECASE | re.DOTALL,
)


class BnEmailParser(EmailParser):
    name = "bn_email"
    version = "1"
    institution = "BN"

    def can_parse(self, message: EmailMessage) -> bool:
        return "bncr.fi.cr" in message.sender.lower()

    def parse(self, message: EmailMessage) -> list[ParsedTransaction]:
        text = strip_accents(" ".join(message.body_text.split()))
        if "compra" not in text.lower():
            return []
        m = _SENTENCE.search(text)
        if not m:
            raise ParseError("notificación de BN con formato no reconocido")
        when = m.group("date") + (f" {m.group('time')}" if m.group("time") else "")
        txn_date, occurred_at = parse_cr_datetime(when)
        kind = (
            AccountKind.DEBIT_CARD
            if m.group("kind").lower() == "debito"
            else AccountKind.CREDIT_CARD
        )
        return [
            ParsedTransaction(
                institution=self.institution,
                account_kind=kind,
                last4=m.group("last4"),
                txn_date=txn_date,
                occurred_at=occurred_at,
                amount=-abs(parse_amount(m.group("amount"))),
                currency=normalize_currency(m.group("cur")),
                merchant=m.group("merchant").strip(),
            )
        ]
