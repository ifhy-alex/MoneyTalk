"""Une los módulos: ingesta → categorización. Lo usan la API, la CLI y el scheduler."""

from datetime import date, timedelta
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from moneytalk.ai import claude_from_settings
from moneytalk.categorization.ai import AiCategorizer, ClaudeCategorizer
from moneytalk.categorization.service import categorize
from moneytalk.config import Settings, get_settings
from moneytalk.ingestion import service
from moneytalk.ingestion.gmail import GmailSource, MailSource, build_query
from moneytalk.models import RawDocument, SourceType, Transaction


@lru_cache
def default_categorizer() -> AiCategorizer | None:
    client = claude_from_settings(get_settings())
    return ClaudeCategorizer(client) if client else None


def on_new_transaction(db: Session, txn: Transaction) -> None:
    categorize(db, txn, default_categorizer())


def ingest_gmail(
    db: Session,
    settings: Settings,
    newer_than: date | None = None,
    source: MailSource | None = None,
) -> service.IngestResult:
    if newer_than is None:
        last = db.scalar(
            select(func.max(RawDocument.received_at)).where(
                RawDocument.source_type == SourceType.EMAIL
            )
        )
        # Un día de traslape: Gmail filtra `after:` por fecha, no por hora.
        newer_than = (
            (last.date() - timedelta(days=1))
            if last
            else date.today() - timedelta(days=settings.gmail_initial_days)  # noqa: DTZ011
        )
    mail = source or GmailSource(settings.gmail_token_file)
    return service.ingest_emails(
        db,
        mail.fetch(build_query(settings.gmail_label, extra_senders(settings), newer_than)),
        on_new=on_new_transaction,
        passwords=pdf_passwords(settings),
    )


def extra_senders(settings: Settings) -> list[str]:
    return [s.strip() for s in settings.gmail_extra_senders.split(",") if s.strip()]


def pdf_passwords(settings: Settings) -> list[str]:
    return [p.strip() for p in settings.statement_pdf_passwords.split(",") if p.strip()]


def ingest_inbox(db: Session, settings: Settings) -> service.IngestResult:
    return service.ingest_inbox(
        db, settings.inbox_dir, pdf_passwords(settings), on_new=on_new_transaction
    )
