"""Banco Popular: "Reporte de Movimientos" de cuentas (exportado desde la banca en línea).

Formato (una fila por movimiento, columnas separadas por varios espacios):
    18/09/2026 02:30 PM  Compra en Comercio:TERM:REF:NOMBRE  FT2626194BWC\\BNK
        ₡19,050.00  ₡0.00  ₡173,367.96      (débito, crédito, saldo; todo en una línea)
Débito y crédito vienen en columnas separadas; el saldo permite validar cada fila.
"""

import re
from datetime import datetime

from moneytalk.ingestion.parsers.base import ParseError, StatementParser
from moneytalk.ingestion.parsers.common import CR_TZ
from moneytalk.ingestion.privacy import iban_bank_code
from moneytalk.ingestion.text import normalize_currency, parse_amount, strip_accents
from moneytalk.ingestion.types import ParsedTransaction
from moneytalk.models.accounts import AccountKind

POPULAR_BANK_CODE = "161"
_MONEY = r"[₡$]\s?-?[\d,]+\.\d{2}"
_ROW = re.compile(
    r"^\s*(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<time>\d{1,2}:\d{2}\s?[AP]M)\s+(?P<desc>.+?)\s{2,}"
    rf"(?P<doc>\S+)\s+(?P<debit>{_MONEY})\s+(?P<credit>{_MONEY})\s+(?P<balance>{_MONEY})\s*$"
)
_ACCOUNT = re.compile(r"Cuenta:\s+\*{0,4}(\d{4})\b")
_CURRENCY = re.compile(r"Moneda:\s+(CRC|USD)")
_INITIAL = re.compile(rf"Saldo Inicial\s+{_MONEY}\s+{_MONEY}\s+(?P<balance>{_MONEY})")
_SINPE_NOTE = re.compile(r"DESCRIPCION\s*(.*)$", re.IGNORECASE)


def clean_description(desc: str) -> str:
    """Saca el comercio de 'Compra en Comercio:TERMINAL:REF:NOMBRE' y limpia referencias."""
    desc = re.sub(r"\s*Saldo Final\s*$", "", desc).strip()
    upper = strip_accents(desc).upper()
    if upper.startswith(("COMPRA EN COMERCIO:", "CARGOS Y COMISIONES:")):
        prefix = "COMISION " if upper.startswith("CARGOS") else ""
        return prefix + dedupe_truncated(desc.split(":")[-1].strip())
    if upper.startswith("SINPE MOVIL INTERNO"):
        note = _SINPE_NOTE.search(desc)
        detail = note.group(1).strip() if note else ""
        return f"SINPE MOVIL {detail}".strip()
    return desc


def dedupe_truncated(name: str) -> str:
    """El banco concatena el nombre truncado con el completo:
    'NOVA SAN JOSE CRNOVA SAN JOSE' → 'NOVA SAN JOSE CR'
    'FS SUPERCFS SUPERCELLSTORE fsprg nl' → 'FS SUPERCELLSTORE fsprg nl'"""
    best: tuple[int, str] | None = None
    for k in range(4, len(name) - 3):
        head, tail = name[:k], name[k:]
        overlap = min(len(head), len(tail))
        if overlap >= 4 and (tail.startswith(head) or head.startswith(tail)):
            candidate = head if len(head) >= len(tail) else tail
            if best is None or overlap > best[0]:
                best = (overlap, candidate)
    return (best[1] if best else name).strip()


class PopularStatementParser(StatementParser):
    name = "popular_movimientos"
    version = "1"
    institution = "POPULAR"

    def can_parse(self, text: str) -> bool:
        head = strip_accents(text[:3000]).upper()
        return "REPORTE DE MOVIMIENTOS" in head and (
            iban_bank_code(text) == POPULAR_BANK_CODE or "\\BNK" in text
        )

    def parse(self, text: str) -> list[ParsedTransaction]:
        account = _ACCOUNT.search(text)
        if not account:
            raise ParseError("no se encontró la cuenta (últimos 4 dígitos)")
        cur = _CURRENCY.search(text)
        currency = normalize_currency(cur.group(1)) if cur else "CRC"
        kind = (
            AccountKind.SAVINGS if "AHORRO" in strip_accents(text).upper() else AccountKind.CHECKING
        )
        initial = _INITIAL.search(text)
        balance = parse_amount(initial.group("balance")) if initial else None

        results: list[ParsedTransaction] = []
        for line_no, line in enumerate(text.splitlines()):
            m = _ROW.match(line)
            if not m:
                continue
            debit, credit = parse_amount(m.group("debit")), parse_amount(m.group("credit"))
            amount = credit - debit
            new_balance = parse_amount(m.group("balance"))
            if balance is not None and balance + amount != new_balance:
                raise ParseError(
                    f"línea {line_no}: el saldo no cuadra ({balance} + {amount} ≠ {new_balance})"
                )
            balance = new_balance
            when = datetime.strptime(
                f"{m.group('date')} {m.group('time')}", "%d/%m/%Y %I:%M %p"
            ).replace(tzinfo=CR_TZ)
            results.append(
                ParsedTransaction(
                    institution=self.institution,
                    account_kind=kind,
                    last4=account.group(1),
                    txn_date=when.date(),
                    occurred_at=when,
                    amount=amount,
                    currency=currency,
                    merchant=clean_description(m.group("desc")),
                    reference=m.group("doc"),
                    line_no=line_no,
                    extra={"descripcion_original": m.group("desc").strip()},
                )
            )
        if not results:
            raise ParseError("el reporte no contiene movimientos reconocibles")
        return results
