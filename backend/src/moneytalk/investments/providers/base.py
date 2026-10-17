"""Capa de abstracción de datos de mercado.

Todos los proveedores devuelven las mismas estructuras con las mismas *unidades*:
ratios como fracción (ROE 0.25 = 25 %), deuda/patrimonio como cociente (1.5 = 150 %),
montos en la moneda del emisor. Cada proveedor documenta cómo normaliza los suyos.
"""

import math
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Protocol


class ProviderError(Exception):
    """El proveedor no respondió o no tiene el símbolo."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    currency: str
    as_of: date
    name: str | None = None


@dataclass(frozen=True)
class Fundamentals:
    symbol: str
    source: str
    as_of: date
    name: str | None = None
    currency: str | None = None
    sector: str | None = None
    country: str | None = None
    market_cap: float | None = None
    pe: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    free_cash_flow: float | None = None
    fcf_yield: float | None = None
    revenue_growth: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    # De dónde salió cada valor cuando no es el proveedor principal (p. ej. "SEC 10-K 2025").
    provenance: dict[str, str] = field(default_factory=dict)

    METRICS: ClassVar[tuple[str, ...]] = (
        "pe",
        "roe",
        "debt_to_equity",
        "free_cash_flow",
        "fcf_yield",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "dividend_yield",
        "payout_ratio",
        "market_cap",
    )

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["as_of"] = self.as_of.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Fundamentals":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean["as_of"] = date.fromisoformat(clean["as_of"])
        return cls(**clean)


@dataclass(frozen=True)
class PriceBar:
    day: date
    close: Decimal  # ajustado por dividendos y splits cuando el proveedor lo permite


class MarketDataProvider(Protocol):
    name: str

    def quote(self, symbol: str) -> Quote: ...

    def fundamentals(self, symbol: str) -> Fundamentals: ...

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]: ...


def to_float(value: Any) -> float | None:
    """Convierte respuestas heterogéneas ('None', '-', '', NaN) a float o None."""
    if value is None or value in ("", "None", "-", "N/A"):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f
