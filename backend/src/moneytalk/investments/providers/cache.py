"""Decorador de caché en Postgres para cualquier proveedor."""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.investments.providers.base import (
    Fundamentals,
    MarketDataProvider,
    PriceBar,
    Quote,
)
from moneytalk.models import MarketCache

log = logging.getLogger(__name__)


class CachedProvider:
    def __init__(self, inner: MarketDataProvider, db: Session, ttl: timedelta) -> None:
        self.inner = inner
        self.name = inner.name
        self._db = db
        self._ttl = ttl

    def _row(self, kind: str, symbol: str, key: str = "") -> MarketCache | None:
        return self._db.scalar(
            select(MarketCache).where(
                MarketCache.provider == self.name,
                MarketCache.kind == kind,
                MarketCache.symbol == symbol,
                MarketCache.cache_key == key,
            )
        )

    def _fresh(self, row: MarketCache | None, ttl: timedelta | None = None) -> bool:
        return row is not None and datetime.now(UTC) - row.fetched_at < (ttl or self._ttl)

    def _store(
        self, row: MarketCache | None, kind: str, symbol: str, key: str, payload: Any
    ) -> None:
        if row is None:
            row = MarketCache(provider=self.name, kind=kind, symbol=symbol, cache_key=key)
            self._db.add(row)
        row.payload = payload
        row.fetched_at = datetime.now(UTC)
        self._db.commit()

    def quote(self, symbol: str) -> Quote:
        row = self._row("quote", symbol)
        if row is None or not self._fresh(row, min(self._ttl, timedelta(hours=1))):
            q = self.inner.quote(symbol)
            payload = {
                "price": str(q.price),
                "currency": q.currency,
                "as_of": q.as_of.isoformat(),
                "name": q.name,
            }
            self._store(row, "quote", symbol, "", payload)
            return q
        p = row.payload
        return Quote(
            symbol,
            Decimal(p["price"]),
            p["currency"],
            date.fromisoformat(p["as_of"]),
            p.get("name"),
        )

    def fundamentals(self, symbol: str) -> Fundamentals:
        row = self._row("fundamentals", symbol)
        if row is not None and self._fresh(row):
            return Fundamentals.from_json(row.payload)
        f = self.inner.fundamentals(symbol)
        self._store(row, "fundamentals", symbol, "", f.to_json())
        return f

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Cachea la serie más larga pedida y recorta; historia vieja no cambia, así que
        solo se refresca si el rango pedido supera lo guardado o el TTL venció."""
        requested_start = start
        row = self._row("history", symbol, "daily")
        if row is not None:
            payload = row.payload
            cached_start = date.fromisoformat(payload["start"])
            cached_end = date.fromisoformat(payload["end"])
            covers = cached_start <= start and (cached_end >= end or self._fresh(row))
            if covers:
                return [
                    PriceBar(date.fromisoformat(d), Decimal(c))
                    for d, c in payload["bars"]
                    if start <= date.fromisoformat(d) <= end
                ]
            start = min(start, cached_start)
        bars = self.inner.history(symbol, start, end)
        self._store(
            row,
            "history",
            symbol,
            "daily",
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "bars": [[b.day.isoformat(), str(b.close)] for b in bars],
            },
        )
        return [b for b in bars if requested_start <= b.day <= end]
