"""BAC Credomatic: notificaciones de transacción por correo y estado de cuenta de tarjeta.

Los formatos se basan en la estructura típica de BAC (tabla Etiqueta/Valor en el correo,
tabla Fecha/Concepto/Moneda/Monto en el PDF). Ajustá las expresiones con ejemplos reales
anonimizados en `tests/fixtures/` cuando el banco cambie el formato; subí `version`.
"""

import re
from decimal import Decimal

from moneytalk.ingestion.parsers.base import EmailParser, ParseError, StatementParser
from moneytalk.ingestion.parsers.common import label_fields, parse_cr_datetime
from moneytalk.ingestion.text import normalize_currency, parse_amount, strip_accents
from moneytalk.ingestion.types import EmailMessage, ParsedTransaction
from moneytalk.models.accounts import AccountKind

_CARD = re.compile(r"(VISA|MASTERCARD|MASTER CARD|AMEX|AMERICAN EXPRESS)\s*[\s:]*[*Xx\- ]+(\d{4})")
_AMOUNT = re.compile(r"(CRC|USD|COL|US\$|₡|\$)\s*(-?[\d.,]+)")
_CREDIT_TYPES = ("DEVOLUCION", "REVERSION", "REVERSO", "ABONO", "CREDITO", "ANULACION")


class BacEmailParser(EmailParser):
    name = "bac_email"
    version = "1"
    institution = "BAC"

    def can_parse(self, message: EmailMessage) -> bool:
        sender = message.sender.lower()
        return "baccredomatic" in sender or "notificacionesbaccr" in sender

    def parse(self, message: EmailMessage) -> list[ParsedTransaction]:
        text = message.body_text
        fields = label_fields(
            text,
            ["Comercio", "Fecha", "Monto", "Autorización", "Referencia", "Tipo de Transacción"],
        )
        if "Monto" not in fields or "Comercio" not in fields:
            return []  # correo de BAC que no es una notificación de compra

        card = _CARD.search(strip_accents(text).upper())
        if not card:
            raise ParseError("no se encontró la tarjeta (últimos 4 dígitos)")
        amount_match = _AMOUNT.search(fields["Monto"])
        if not amount_match:
            raise ParseError(f"monto ilegible: {fields['Monto']!r}")

        txn_type = strip_accents(fields.get("Tipo de Transacción", "COMPRA")).upper()
        amount = abs(parse_amount(amount_match.group(2)))
        signed = amount if txn_type.startswith(_CREDIT_TYPES) else -amount
        txn_date, occurred_at = parse_cr_datetime(fields.get("Fecha", ""))
        kind = (
            AccountKind.DEBIT_CARD
            if "DEBITO" in strip_accents(text).upper()
            else AccountKind.CREDIT_CARD
        )

        return [
            ParsedTransaction(
                institution=self.institution,
                account_kind=kind,
                last4=card.group(2),
                txn_date=txn_date,
                occurred_at=occurred_at,
                amount=signed,
                currency=normalize_currency(amount_match.group(1)),
                merchant=fields["Comercio"],
                reference=fields.get("Autorización") or fields.get("Referencia"),
                extra={"tipo": txn_type},
            )
        ]


_STMT_CARD = re.compile(r"TARJETA[^\n]*?(\d{4})\b")
_STMT_LINE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+?)\s+(?P<cur>CRC|USD)\s+(?P<amount>-?[\d,]+\.\d{2})\s*$"
)


class BacStatementParser(StatementParser):
    """Estado de cuenta de tarjeta de crédito. Cargos positivos en el PDF = salidas de dinero."""

    name = "bac_statement"
    version = "1"
    institution = "BAC"

    def can_parse(self, text: str) -> bool:
        head = strip_accents(text[:2000]).upper()
        return "BAC" in head and "ESTADO DE CUENTA" in head

    def parse(self, text: str) -> list[ParsedTransaction]:
        upper = strip_accents(text).upper()
        card = _STMT_CARD.search(upper)
        if not card:
            raise ParseError("no se encontró el número de tarjeta en el estado de cuenta")
        results: list[ParsedTransaction] = []
        for line_no, line in enumerate(text.splitlines()):
            m = _STMT_LINE.match(line.strip())
            if not m:
                continue
            txn_date, _ = parse_cr_datetime(m.group("date"))
            statement_amount = parse_amount(m.group("amount"))
            results.append(
                ParsedTransaction(
                    institution=self.institution,
                    account_kind=AccountKind.CREDIT_CARD,
                    last4=card.group(1),
                    txn_date=txn_date,
                    amount=-statement_amount if statement_amount else Decimal("0"),
                    currency=m.group("cur"),
                    merchant=m.group("desc").strip(),
                    line_no=line_no,
                )
            )
        if not results:
            raise ParseError("el estado de cuenta no contiene líneas de transacciones reconocibles")
        return results
