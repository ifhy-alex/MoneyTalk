"""Proceso `worker`: tareas programadas con APScheduler (zona horaria de Costa Rica).

Celery no se justifica: un solo usuario, pocas tareas, sin colas distribuidas.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from moneytalk.config import Settings, get_settings
from moneytalk.db import get_sessionmaker
from moneytalk.investments.jobs import job_refresh_quotes
from moneytalk.jobs import (
    job_alerts,
    job_fx_sync,
    job_inbox,
    job_ingest_and_alert,
    job_weekly_summary,
)
from moneytalk.log import configure_logging

log = logging.getLogger("moneytalk.scheduler")


def _run(name: str, fn: Callable[[Session, Settings], object]) -> Callable[[], None]:
    def wrapper() -> None:
        settings = get_settings()
        with get_sessionmaker()() as db:
            try:
                fn(db, settings)
            except Exception:
                log.exception("La tarea %s falló", name)
                db.rollback()

    return wrapper


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    tz = settings.app_timezone
    sched = BlockingScheduler(timezone=tz)
    sched.add_job(
        _run("gmail+alertas", job_ingest_and_alert),
        IntervalTrigger(minutes=30),
        id="ingest",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _run("carpeta de entrada", job_inbox),
        IntervalTrigger(minutes=2),
        id="inbox",
        max_instances=1,
        coalesce=True,
    )
    # BCCR publica una vez al día; el respaldo de mercado se refresca cada hora.
    fx_trigger = (
        CronTrigger(hour=8, minute=5, timezone=tz)
        if settings.bccr_token
        else IntervalTrigger(hours=1)
    )
    sched.add_job(
        _run("tipo de cambio", job_fx_sync),
        fx_trigger,
        id="fx",
        next_run_time=datetime.now(UTC),  # también al arrancar
    )
    sched.add_job(
        _run("alertas presupuesto", job_alerts),
        CronTrigger(hour=19, minute=0, timezone=tz),
        id="alerts",
    )
    sched.add_job(
        _run("resumen semanal", job_weekly_summary),
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=tz),
        id="weekly",
    )
    sched.add_job(
        _run("cotizaciones", job_refresh_quotes),
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=tz),
        id="quotes",
    )
    return sched


def main() -> None:
    configure_logging(get_settings().log_level)
    sched = build_scheduler()
    log.info("Scheduler iniciado con %s tareas", len(sched.get_jobs()))
    sched.start()


if __name__ == "__main__":
    main()
