"""Tareas programadas de inversiones."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.investments.providers import ProviderError, cached_provider
from moneytalk.models import Asset

log = logging.getLogger(__name__)


def job_refresh_quotes(db: Session, settings: Settings) -> int:
    """Precalienta la caché de cotizaciones del portafolio una vez al día (cierre de EE. UU.)."""
    provider = cached_provider(db, settings)
    ok = 0
    for symbol in db.scalars(select(Asset.symbol).where(Asset.manual_price.is_(None))):
        try:
            provider.quote(symbol)
            ok += 1
        except ProviderError as exc:
            log.warning("Cotización fallida: %s", exc)
    return ok
