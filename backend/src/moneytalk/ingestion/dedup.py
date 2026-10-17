"""Deduplicación entre fuentes.

El mismo gasto llega por correo (el día de la compra, con hora y autorización) y luego en
el estado de cuenta (a veces con fecha de posteo 1-3 días después y otro nombre de comercio).
Regla: misma cuenta + misma moneda + mismo monto exacto + fecha dentro de la ventana +
*distinto tipo de fuente*. Dos correos iguales el mismo día NO se fusionan: pueden ser dos
cafés de verdad. Entre los candidatos gana el de mayor puntaje (fecha + comercio).
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from moneytalk.ingestion.merchant import merchant_similarity
from moneytalk.ingestion.types import ParsedTransaction
from moneytalk.models import RawDocument, SourceType, Transaction, TransactionSource

DATE_WINDOW_DAYS = 3
MIN_CONFIDENCE = Decimal("0.60")


@dataclass(frozen=True)
class DuplicateMatch:
    transaction: Transaction
    confidence: Decimal


def _score(parsed: ParsedTransaction, candidate: Transaction) -> Decimal:
    for src in candidate.sources:
        ref = src.extracted.get("reference")
        if parsed.reference and ref and ref == parsed.reference:
            return Decimal("1.00")
    day_gap = abs((candidate.txn_date - parsed.txn_date).days)
    date_score = 1 - day_gap / (DATE_WINDOW_DAYS + 1)
    name_score = merchant_similarity(parsed.merchant, candidate.merchant_raw)
    score = 0.5 + 0.3 * date_score + 0.2 * name_score
    return Decimal(str(round(score, 2)))


def find_duplicate(
    db: Session, account_id: int, parsed: ParsedTransaction, source_type: SourceType
) -> DuplicateMatch | None:
    window = timedelta(days=DATE_WINDOW_DAYS)
    candidates = db.scalars(
        select(Transaction)
        .where(
            Transaction.account_id == account_id,
            Transaction.currency == parsed.currency,
            Transaction.amount == parsed.amount,
            Transaction.txn_date.between(parsed.txn_date - window, parsed.txn_date + window),
        )
        .options(selectinload(Transaction.sources).selectinload(TransactionSource.raw_document))
    ).all()

    best: DuplicateMatch | None = None
    for cand in candidates:
        source_types = {
            s.raw_document.source_type
            for s in cand.sources
            if isinstance(s.raw_document, RawDocument)
        }
        if source_type in source_types:
            continue
        score = _score(parsed, cand)
        if score >= MIN_CONFIDENCE and (best is None or score > best.confidence):
            best = DuplicateMatch(cand, score)
    return best
