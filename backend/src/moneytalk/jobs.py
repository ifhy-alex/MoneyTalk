"""Tareas que corren el scheduler, la CLI y algunos endpoints."""

import logging
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.finance.alerts import run_alerts
from moneytalk.finance.fx import (
    FxConverter,
    FxSource,
    default_source,
    default_sync_window,
    sync_rates,
)
from moneytalk.finance.prefs import get_prefs
from moneytalk.finance.summary import weekly_summary
from moneytalk.models import Alert
from moneytalk.notifications.telegram import TelegramNotifier, esc
from moneytalk.pipeline import ingest_gmail, ingest_inbox

log = logging.getLogger(__name__)


def today_cr(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def job_fx_sync(db: Session, settings: Settings, source: FxSource | None = None) -> int:
    start, end = default_sync_window(db, today_cr(settings))
    src = source or default_source(settings)
    n = sync_rates(db, src, start, end)
    log.info("Tipo de cambio (%s): %s días actualizados", src.label, n)
    return n


def job_alerts(
    db: Session, settings: Settings, notifier: TelegramNotifier | None = None
) -> list[Alert]:
    prefs = get_prefs(db)
    created = run_alerts(db, FxConverter(db), prefs, today_cr(settings))
    notifier = notifier or TelegramNotifier(settings)
    if prefs.telegram_alerts and notifier.enabled:
        pending = db.scalars(select(Alert).where(Alert.notified_at.is_(None))).all()
        for alert in pending:
            if notifier.send(f"⚠️ {esc(alert.message)}"):
                alert.notified_at = datetime.now(UTC)
        db.commit()
    return created


def job_inbox(db: Session, settings: Settings) -> None:
    result = ingest_inbox(db, settings)
    if result.documents_new or result.documents_failed:
        log.info(
            "Carpeta de entrada: %s PDF nuevos, %s transacciones, %s errores",
            result.documents_new,
            result.transactions_created,
            result.documents_failed,
        )
        job_alerts(db, settings)


def job_ingest_and_alert(db: Session, settings: Settings) -> None:
    if settings.gmail_token_file.exists():
        result = ingest_gmail(db, settings)
        log.info(
            "Gmail: %s nuevos, %s transacciones, %s fusionadas, %s errores",
            result.documents_new,
            result.transactions_created,
            result.transactions_merged,
            result.documents_failed,
        )
    job_alerts(db, settings)


def job_weekly_summary(
    db: Session, settings: Settings, notifier: TelegramNotifier | None = None
) -> str:
    text = weekly_summary(db, FxConverter(db), today_cr(settings))
    (notifier or TelegramNotifier(settings)).send(text)
    return text
