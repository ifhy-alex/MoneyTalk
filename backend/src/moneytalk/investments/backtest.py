"""Backtesting de criterios del screener con datos históricos.

Método:
- Rebalanceo anual en un mes fijo. En cada fecha se calculan las métricas con los 10-K
  *presentados antes de esa fecha* en SEC EDGAR (point-in-time, sin anticipación) y el P/E
  con el precio de ese día y el EPS diluido del último 10-K disponible.
- Se compran a partes iguales las empresas que cumplen TODOS los criterios (dato faltante =
  no cumple) y se mantienen hasta el siguiente rebalanceo.
- Se compara contra el índice de referencia y contra el universo completo a partes iguales:
  si la estrategia no le gana al universo, los criterios no agregaron valor.

Limitaciones que el resultado reporta siempre: sesgo de supervivencia (el universo es la
lista de hoy), sobreajuste, pocas observaciones, sin costos ni impuestos.
"""

import bisect
import itertools
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

from moneytalk.investments.edgar import compute_official
from moneytalk.investments.providers.base import MarketDataProvider, PriceBar, ProviderError
from moneytalk.investments.screener import Criterion, evaluate

# Métricas que se pueden reconstruir históricamente desde EDGAR + precios.
SUPPORTED = {
    "pe",
    "roe",
    "debt_to_equity",
    "free_cash_flow",
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
}


class BacktestRequest(BaseModel):
    criteria: list[Criterion] = Field(min_length=1)
    universe: list[str] = Field(min_length=2, max_length=100)
    start_year: int = Field(ge=2010)
    end_year: int
    rebalance_month: int = Field(default=4, ge=1, le=12)  # abril: la mayoría ya presentó su 10-K
    benchmark: str = "SPY"


@dataclass
class Period:
    start: date
    end: date
    holdings: list[str]
    evidence: dict[str, dict[str, float | None]]
    strategy_return: float | None
    universe_return: float | None
    benchmark_return: float | None


@dataclass
class BacktestResult:
    periods: list[Period]
    curve: list[dict[str, Any]]
    stats: dict[str, dict[str, float | None]]
    warnings: list[str]
    unsupported_criteria: list[str]
    skipped_symbols: dict[str, str] = field(default_factory=dict)


FactsLoader = Any  # Callable[[str], tuple[int, dict]] — EdgarClient.company_facts


def _price_on(bars: list[PriceBar], day: date) -> float | None:
    """Último cierre en o antes de `day` (máx. 7 días de antigüedad)."""
    days = [b.day for b in bars]
    idx = bisect.bisect_right(days, day) - 1
    if idx < 0 or (day - bars[idx].day).days > 7:
        return None
    return float(bars[idx].close)


def _ret(bars: list[PriceBar], a: date, b: date) -> float | None:
    pa, pb = _price_on(bars, a), _price_on(bars, b)
    return pb / pa - 1 if pa and pb else None


def _metrics_at(
    facts: dict[str, Any], symbol: str, as_of: date, price: float | None
) -> dict[str, float | None]:
    off = compute_official(symbol, 0, facts, as_of=as_of)
    m = dict(off.metrics)
    eps = m.pop("eps_diluted", None)
    m["pe"] = price / eps if price and eps else (None if eps is None else -1.0)
    return m


def _stats(returns: list[float]) -> dict[str, float | None]:
    if not returns:
        return {"cagr": None, "volatility": None, "max_drawdown": None, "total": None}
    value, peak, mdd = 1.0, 1.0, 0.0
    for r in returns:
        value *= 1 + r
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    return {
        "total": value - 1,
        "cagr": value ** (1 / len(returns)) - 1,
        "volatility": statistics.pstdev(returns) if len(returns) > 1 else None,
        "max_drawdown": mdd,
    }


def run_backtest(
    req: BacktestRequest, provider: MarketDataProvider, facts_loader: FactsLoader, today: date
) -> BacktestResult:
    unsupported = [c.describe() for c in req.criteria if c.metric not in SUPPORTED]
    criteria = [c for c in req.criteria if c.metric in SUPPORTED]
    dates = [date(y, req.rebalance_month, 1) for y in range(req.start_year, req.end_year + 1)]
    dates = [d for d in dates if d < today] + [
        min(date(req.end_year + 1, req.rebalance_month, 1), today)
    ]
    if len(dates) < 2:
        raise ValueError("El rango no alcanza para un periodo completo")

    span = (dates[0] - timedelta(days=10), dates[-1])
    bench = provider.history(req.benchmark, *span)
    prices: dict[str, list[PriceBar]] = {}
    facts: dict[str, dict[str, Any]] = {}
    skipped: dict[str, str] = {}
    for raw in req.universe:
        sym = raw.upper()
        try:
            prices[sym] = provider.history(sym, *span)
            facts[sym] = facts_loader(sym)[1]
        except ProviderError as exc:
            skipped[sym] = str(exc)

    periods: list[Period] = []
    for start, end in itertools.pairwise(dates):
        evidence: dict[str, dict[str, float | None]] = {}
        holdings: list[str] = []
        available: list[str] = []
        for sym, bars in prices.items():
            px = _price_on(bars, start)
            if px is None:
                continue  # aún no cotizaba
            available.append(sym)
            try:
                m = _metrics_at(facts[sym], sym, start, px)
            except ProviderError:
                continue
            evidence[sym] = {c.metric: m.get(c.metric) for c in criteria}
            if criteria and all(evaluate(c, m.get(c.metric)) is True for c in criteria):
                holdings.append(sym)

        def avg(symbols: list[str], a: date = start, b: date = end) -> float | None:
            rets = [r for s in symbols if (r := _ret(prices[s], a, b)) is not None]
            return sum(rets) / len(rets) if rets else None

        periods.append(
            Period(
                start,
                end,
                sorted(holdings),
                evidence,
                avg(holdings) if holdings else 0.0,  # sin candidatos = efectivo
                avg(available),
                _ret(bench, start, end),
            )
        )

    curve: list[dict[str, Any]] = []
    values = {"strategy": 1.0, "universe": 1.0, "benchmark": 1.0}
    curve.append({"date": dates[0].isoformat(), **values})
    for p in periods:
        for key, r in (
            ("strategy", p.strategy_return),
            ("universe", p.universe_return),
            ("benchmark", p.benchmark_return),
        ):
            values[key] *= 1 + (r or 0.0)
        curve.append({"date": p.end.isoformat(), **{k: round(v, 4) for k, v in values.items()}})

    def series(attr: str) -> list[float]:
        return [getattr(p, attr) for p in periods if getattr(p, attr) is not None]

    stats = {
        "strategy": _stats(series("strategy_return")),
        "universe": _stats(series("universe_return")),
        "benchmark": _stats(series("benchmark_return")),
    }
    return BacktestResult(
        periods,
        curve,
        stats,
        _warnings(req, periods, criteria, unsupported, skipped),
        unsupported,
        skipped,
    )


def _warnings(
    req: BacktestRequest,
    periods: list[Period],
    criteria: list[Criterion],
    unsupported: list[str],
    skipped: dict[str, str],
) -> list[str]:
    w = [
        "Sesgo de supervivencia: el universo son empresas que existen hoy. Las que quebraron o "
        "fueron absorbidas no aparecen, lo que infla los resultados históricos.",
        "Sin costos de transacción, impuestos (30 % de retención sobre dividendos para no "
        "residentes en EE. UU.) ni tipo de cambio.",
    ]
    n = len(periods)
    if n < 10:
        w.append(
            f"Solo {n} periodos anuales: con tan pocas observaciones una diferencia de rendimiento "
            "puede ser azar. No es evidencia estadística."
        )
    if len(criteria) >= 4 and n < 3 * len(criteria):
        w.append(
            f"Riesgo de sobreajuste: {len(criteria)} criterios para {n} periodos. Si ajustaste los "
            "umbrales mirando este resultado, el desempeño fuera de muestra probablemente sea peor."
        )
    holding_counts = [len(p.holdings) for p in periods]
    if holding_counts and statistics.mean(holding_counts) < 5:
        w.append(
            f"Concentración: en promedio {statistics.mean(holding_counts):.1f} empresas por "
            "periodo; pocos nombres hacen que el resultado dependa de casos individuales."
        )
    empty = sum(1 for c in holding_counts if c == 0)
    if empty:
        w.append(
            f"En {empty} periodo(s) ninguna empresa cumplió los criterios (se asume efectivo, 0 %)."
        )
    if len(req.universe) < 20:
        w.append(f"Universo pequeño ({len(req.universe)} símbolos).")
    if unsupported:
        w.append(
            "Criterios no reconstruibles históricamente, ignorados: " + "; ".join(unsupported) + "."
        )
    if skipped:
        w.append(f"{len(skipped)} símbolo(s) sin datos (precios o SEC) fueron excluidos.")
    strategy = [p.strategy_return for p in periods if p.strategy_return is not None]
    universe = [p.universe_return for p in periods if p.universe_return is not None]
    if strategy and universe:
        beat = sum(1 for p in periods if (p.strategy_return or 0) > (p.universe_return or 0))
        w.append(f"La estrategia superó al universo en {beat} de {n} periodos.")
    if any(math.isnan(x) for x in strategy):
        w.append("Hay retornos inválidos (NaN) en algún periodo.")
    return w
