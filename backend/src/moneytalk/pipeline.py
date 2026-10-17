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
from moneytalk.ingestion.gmail import GmailSource, MailSource
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
        newer_than = (last.date() - timedelta(days=1)) if last else None
    mail = source or GmailSource(settings.gmail_token_file)
    return service.ingest_emails(
        db, mail.fetch(settings.gmail_label, newer_than), on_new=on_new_transaction
    )
