"""Screener fundamental con criterios explícitos y auditables.

Cada resultado lista qué criterio se evaluó, el umbral, el valor real y su fuente. Un dato
faltante NO cuenta como cumplido: se marca "sin dato" para que no pase desapercibido.
Esto produce *señales según tus criterios*, no recomendaciones de compra o venta.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from moneytalk.investments.edgar import OfficialFundamentals
from moneytalk.investments.providers.base import Fundamentals

Metric = Literal[
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
]
Op = Literal[">=", "<=", ">", "<", "between"]

METRIC_LABELS: dict[str, tuple[str, str]] = {
    # métrica: (etiqueta, formato) — formato "pct" | "ratio" | "money"
    "pe": ("P/E (precio/utilidad)", "ratio"),
    "roe": ("ROE (rentabilidad sobre patrimonio)", "pct"),
    "debt_to_equity": ("Deuda / patrimonio", "ratio"),
    "free_cash_flow": ("Flujo de caja libre", "money"),
    "fcf_yield": ("Rendimiento del flujo libre (FCF / cap.)", "pct"),
    "revenue_growth": ("Crecimiento de ingresos (anual)", "pct"),
    "gross_margin": ("Margen bruto", "pct"),
    "operating_margin": ("Margen operativo", "pct"),
    "net_margin": ("Margen neto", "pct"),
    "dividend_yield": ("Rendimiento por dividendo", "pct"),
    "payout_ratio": ("Payout (dividendos / utilidad)", "pct"),
    "market_cap": ("Capitalización de mercado", "money"),
}


class Criterion(BaseModel):
    metric: Metric
    op: Op
    value: float
    value_max: float | None = None  # solo para "between"

    @model_validator(mode="after")
    def _check_between(self) -> "Criterion":
        if self.op == "between" and (self.value_max is None or self.value_max < self.value):
            raise ValueError("'between' requiere value_max >= value")
        return self

    def describe(self) -> str:
        label = METRIC_LABELS[self.metric][0]
        if self.op == "between":
            return f"{label} entre {self.value:g} y {self.value_max:g}"
        return f"{label} {self.op} {self.value:g}"


class ScreenerRequest(BaseModel):
    criteria: list[Criterion] = Field(min_length=1)
    universe: list[str] = Field(min_length=1, max_length=200)
    use_sec: bool = True  # sobrescribir con datos oficiales de la SEC cuando existan


_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


@dataclass(frozen=True)
class CriterionResult:
    metric: str
    label: str
    description: str
    actual: float | None
    passed: bool | None  # None = sin dato
    source: str


@dataclass(frozen=True)
class ScreenResult:
    symbol: str
    name: str | None
    sector: str | None
    country: str | None
    passed: int
    failed: int
    missing: int
    total: int
    results: list[CriterionResult]
    error: str | None = None

    @property
    def meets_all(self) -> bool:
        return self.passed == self.total


def evaluate(c: Criterion, actual: float | None) -> bool | None:
    if actual is None:
        return None
    if c.op == "between":
        return c.value <= actual <= (c.value_max if c.value_max is not None else c.value)
    # P/E negativo (pérdidas) nunca cumple un tope máximo de P/E.
    if c.metric == "pe" and actual <= 0:
        return False
    return _OPS[c.op](actual, c.value)


def merge_official(
    f: Fundamentals, official: OfficialFundamentals | None
) -> tuple[dict[str, float | None], dict[str, str]]:
    values: dict[str, float | None] = {m: getattr(f, m) for m in Fundamentals.METRICS}
    sources = dict.fromkeys(values, f"{f.source} ({f.as_of:%Y-%m-%d})")
    if official:
        for m, v in official.metrics.items():
            if v is not None:
                values[m] = v
                sources[m] = official.provenance.get(m, "SEC EDGAR")
        if values.get("free_cash_flow") is not None and f.market_cap:
            values["fcf_yield"] = values["free_cash_flow"] / f.market_cap  # type: ignore[operator]
            sources["fcf_yield"] = f"{sources['free_cash_flow']} / cap. {f.source}"
    return values, sources


def screen_one(
    symbol: str,
    criteria: list[Criterion],
    fundamentals: Fundamentals,
    official: OfficialFundamentals | None = None,
) -> ScreenResult:
    values, sources = merge_official(fundamentals, official)
    results = []
    for c in criteria:
        actual = values.get(c.metric)
        results.append(
            CriterionResult(
                metric=c.metric,
                label=METRIC_LABELS[c.metric][0],
                description=c.describe(),
                actual=actual,
                passed=evaluate(c, actual),
                source=sources.get(c.metric, fundamentals.source)
                if actual is not None
                else "sin dato",
            )
        )
    return ScreenResult(
        symbol=symbol,
        name=fundamentals.name,
        sector=fundamentals.sector,
        country=fundamentals.country,
        passed=sum(r.passed is True for r in results),
        failed=sum(r.passed is False for r in results),
        missing=sum(r.passed is None for r in results),
        total=len(results),
        results=results,
    )


DEFAULT_PRESETS: list[dict[str, object]] = [
    {
        "name": "Calidad a precio razonable",
        "criteria": [
            {"metric": "pe", "op": "between", "value": 0, "value_max": 25},
            {"metric": "roe", "op": ">=", "value": 0.15},
            {"metric": "debt_to_equity", "op": "<=", "value": 1.0},
            {"metric": "free_cash_flow", "op": ">", "value": 0},
            {"metric": "revenue_growth", "op": ">=", "value": 0.05},
            {"metric": "net_margin", "op": ">=", "value": 0.10},
        ],
        "universe": ["AAPL", "MSFT", "GOOGL", "JNJ", "PG", "KO", "V", "MA", "COST", "PEP"],
    },
    {
        "name": "Dividendos sostenibles",
        "criteria": [
            {"metric": "dividend_yield", "op": ">=", "value": 0.025},
            {"metric": "payout_ratio", "op": "<=", "value": 0.7},
            {"metric": "debt_to_equity", "op": "<=", "value": 1.5},
            {"metric": "free_cash_flow", "op": ">", "value": 0},
        ],
        "universe": ["KO", "PEP", "JNJ", "PG", "XOM", "CVX", "PFE", "VZ", "MO", "MMM"],
    },
]
