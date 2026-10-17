"""Orquestación de la ingesta: documento crudo → parser → dedup → transacción canónica."""

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from moneytalk.ingestion.dedup import find_duplicate
from moneytalk.ingestion.merchant import normalize_merchant
from moneytalk.ingestion.parsers import (
    ParseError,
    find_email_parser,
    find_statement_parser,
    parser_by_name,
)
from moneytalk.ingestion.parsers.base import EmailParser, StatementParser
from moneytalk.ingestion.pdf import pdf_to_text, sha256_bytes
from moneytalk.ingestion.types import EmailMessage, ParsedTransaction
from moneytalk.models import (
    Account,
    RawDocument,
    RawDocumentStatus,
    SourceType,
    Transaction,
    TransactionSource,
)

log = logging.getLogger(__name__)

# Gancho para que la categorización (Fase 3) procese cada transacción nueva.
NewTransactionHook = Callable[[Session, Transaction], None]


@dataclass
class IngestResult:
    documents_new: int = 0
    documents_skipped: int = 0
    documents_failed: int = 0
    transactions_created: int = 0
    transactions_merged: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, other: "IngestResult") -> None:
        self.documents_new += other.documents_new
        self.documents_skipped += other.documents_skipped
        self.documents_failed += other.documents_failed
        self.transactions_created += other.transactions_created
        self.transactions_merged += other.transactions_merged
        self.errors.extend(other.errors)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_raw(
    db: Session,
    *,
    source_type: SourceType,
    external_id: str,
    content_text: str,
    sender: str | None = None,
    subject: str | None = None,
    received_at: datetime | None = None,
) -> RawDocument | None:
    """Guarda el documento crudo. Devuelve None si ya existía (por id externo o contenido)."""
    content_hash = _hash(content_text)
    exists = db.scalar(
        select(func.count())
        .select_from(RawDocument)
        .where(
            ((RawDocument.source_type == source_type) & (RawDocument.external_id == external_id))
            | (RawDocument.content_hash == content_hash)
        )
    )
    if exists:
        return None
    raw = RawDocument(
        source_type=source_type,
        external_id=external_id,
        content_text=content_text,
        content_hash=content_hash,
        sender=sender,
        subject=subject,
        received_at=received_at,
    )
    db.add(raw)
    db.flush()
    return raw


def _get_or_create_account(db: Session, parsed: ParsedTransaction) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.institution == parsed.institution,
            Account.kind == parsed.account_kind,
            Account.last4 == parsed.last4,
        )
    )
    if account is None:
        account = Account(
            institution=parsed.institution,
            kind=parsed.account_kind,
            last4=parsed.last4,
            currency=parsed.currency,
        )
        db.add(account)
        db.flush()
    return account


def _parse(
    raw: RawDocument,
) -> tuple[EmailParser | StatementParser | None, list[ParsedTransaction]]:
    if raw.source_type is SourceType.EMAIL:
        message = EmailMessage(
            message_id=raw.external_id,
            sender=raw.sender or "",
            subject=raw.subject or "",
            received_at=raw.received_at,
            body_text=raw.content_text,
        )
        email_parser = find_email_parser(message)
        return email_parser, email_parser.parse(message) if email_parser else []
    stmt_parser = find_statement_parser(raw.content_text)
    return stmt_parser, stmt_parser.parse(raw.content_text) if stmt_parser else []


def process_raw(
    db: Session, raw: RawDocument, on_new: NewTransactionHook | None = None
) -> IngestResult:
    result = IngestResult()
    try:
        parser, parsed_list = _parse(raw)
    except (ParseError, ValueError) as exc:
        raw.status = RawDocumentStatus.FAILED
        raw.error = str(exc)
        result.documents_failed += 1
        result.errors.append(f"documento {raw.id}: {exc}")
        log.warning("Fallo al parsear documento %s: %s", raw.id, exc)
        return result

    if parser is None:
        raw.status = RawDocumentStatus.IGNORED
        raw.error = "ningún parser reconoce este documento"
        return result

    raw.parser_name, raw.parser_version = parser.name, parser.version
    for parsed in parsed_list:
        account = _get_or_create_account(db, parsed)
        source = TransactionSource(
            raw_document=raw, line_no=parsed.line_no, extracted=parsed.to_json()
        )
        match = find_duplicate(db, account.id, parsed, raw.source_type)
        if match:
            source.match_confidence = match.confidence
            match.transaction.sources.append(source)
            # El correo trae hora exacta; el estado de cuenta no. Conservar la más precisa.
            if parsed.occurred_at and not match.transaction.occurred_at:
                match.transaction.occurred_at = parsed.occurred_at
            result.transactions_merged += 1
        else:
            txn = Transaction(
                account=account,
                txn_date=parsed.txn_date,
                occurred_at=parsed.occurred_at,
                amount=parsed.amount,
                currency=parsed.currency,
                merchant_raw=parsed.merchant,
                merchant_normalized=normalize_merchant(parsed.merchant),
                sources=[source],
            )
            db.add(txn)
            db.flush()
            if on_new:
                on_new(db, txn)
            result.transactions_created += 1
    raw.status = RawDocumentStatus.PARSED if parsed_list else RawDocumentStatus.IGNORED
    raw.error = None
    return result


def ingest_email(
    db: Session, message: EmailMessage, on_new: NewTransactionHook | None = None
) -> IngestResult:
    raw = store_raw(
        db,
        source_type=SourceType.EMAIL,
        external_id=message.message_id,
        content_text=message.body_text,
        sender=message.sender,
        subject=message.subject,
        received_at=message.received_at,
    )
    if raw is None:
        return IngestResult(documents_skipped=1)
    result = process_raw(db, raw, on_new)
    result.documents_new += 1
    return result


def ingest_emails(
    db: Session, messages: Iterable[EmailMessage], on_new: NewTransactionHook | None = None
) -> IngestResult:
    total = IngestResult()
    for message in messages:
        total.add(ingest_email(db, message, on_new))
        db.commit()
    return total


def ingest_pdf(
    db: Session,
    data: bytes,
    filename: str = "",
    password: str | None = None,
    on_new: NewTransactionHook | None = None,
) -> IngestResult:
    text = pdf_to_text(data, password)
    raw = store_raw(
        db,
        source_type=SourceType.PDF_STATEMENT,
        external_id=sha256_bytes(data),
        content_text=text,
        subject=filename or None,
    )
    if raw is None:
        return IngestResult(documents_skipped=1)
    result = process_raw(db, raw, on_new)
    result.documents_new += 1
    db.commit()
    return result


def reprocess(
    db: Session, raw: RawDocument, on_new: NewTransactionHook | None = None
) -> IngestResult:
    """Vuelve a parsear un documento: borra sus fuentes y las transacciones que queden huérfanas.

    Las transacciones con categoría confirmada que sobrevivan (por tener otra fuente) se conservan.
    """
    txn_ids = list(
        db.scalars(
            select(TransactionSource.transaction_id).where(
                TransactionSource.raw_document_id == raw.id
            )
        )
    )
    db.execute(delete(TransactionSource).where(TransactionSource.raw_document_id == raw.id))
    if txn_ids:
        orphan_ids = db.scalars(
            select(Transaction.id)
            .where(Transaction.id.in_(txn_ids))
            .where(~Transaction.sources.any())
        ).all()
        db.execute(delete(Transaction).where(Transaction.id.in_(orphan_ids)))
    db.expire_all()
    result = process_raw(db, raw, on_new)
    db.commit()
    return result


def outdated_documents(db: Session) -> list[RawDocument]:
    """Documentos fallidos o leídos con una versión de parser más vieja que la actual."""
    docs = db.scalars(
        select(RawDocument).where(
            RawDocument.status.in_([RawDocumentStatus.FAILED, RawDocumentStatus.PARSED])
        )
    ).all()
    stale: list[RawDocument] = []
    for doc in docs:
        if doc.status is RawDocumentStatus.FAILED:
            stale.append(doc)
            continue
        parser = parser_by_name(doc.parser_name or "")
        if parser and parser.version != doc.parser_version:
            stale.append(doc)
    return stale
