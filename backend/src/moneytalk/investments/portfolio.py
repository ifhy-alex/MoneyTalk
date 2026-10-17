"""Portafolio: posiciones derivadas de las operaciones, rendimiento, diversificación y
comparación contra un índice.

Comparación con el S&P 500 ("portafolio sombra"): cada compra/venta se replica con el mismo
monto en el ETF de referencia (SPY por defecto) el mismo día. Al final se compara el valor
actual de ambos. Así la comparación respeta *cuándo* metiste o sacaste plata, que es lo
que una simple variación del índice no captura. Se usan precios ajustados por dividendos.
"""

import bisect
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from moneytalk.finance.fx import FxConverter
from moneytalk.investments.providers.base import MarketDataProvider, PriceBar, ProviderError
from moneytalk.models import Asset, Trade, TradeSide

ZERO = Decimal("0")
BENCHMARK = "SPY"


@dataclass
class Position:
    symbol: str
    name: str | None
    asset_type: str
    currency: str
    sector: str
    country: str
    quantity: Decimal = ZERO
    cost_basis: Decimal = ZERO  # costo total de las unidades vigentes (incluye comisiones)
    realized_pnl: Decimal = ZERO
    price: Decimal | None = None
    price_source: str = ""

    @property
    def avg_cost(self) -> Decimal | None:
        return (
            (self.cost_basis / self.quantity).quantize(Decimal("0.0001")) if self.quantity else None
        )

    @property
    def market_value(self) -> Decimal | None:
        return (
            (self.quantity * self.price).quantize(Decimal("0.01"))
            if self.price is not None
            else None
        )

    @property
    def unrealized_pnl(self) -> Decimal | None:
        mv = self.market_value
        return (mv - self.cost_basis).quantize(Decimal("0.01")) if mv is not None else None


def load_trades(db: Session) -> list[Trade]:
    return list(
        db.scalars(
            select(Trade).options(selectinload(Trade.asset)).order_by(Trade.trade_date, Trade.id)
        )
    )


def build_positions(trades: list[Trade]) -> dict[str, Position]:
    """Costo promedio ponderado. Una venta reduce el costo en proporción y realiza P&L."""
    positions: dict[str, Position] = {}
    for t in trades:
        a = t.asset
        pos = positions.setdefault(
            t.symbol,
            Position(
                t.symbol,
                a.name,
                a.asset_type.value,
                a.currency,
                a.sector or "Sin sector",
                a.country or "Sin país",
            ),
        )
        if t.side is TradeSide.BUY:
            pos.quantity += t.quantity
            pos.cost_basis += t.quantity * t.price + t.fees
        else:
            if t.quantity > pos.quantity:
                raise ValueError(f"Venta de {t.symbol} el {t.trade_date} supera la posición")
            avg = pos.cost_basis / pos.quantity
            proceeds = t.quantity * t.price - t.fees
            pos.realized_pnl += proceeds - avg * t.quantity
            pos.cost_basis -= avg * t.quantity
            pos.quantity -= t.quantity
    return positions


def price_positions(
    positions: dict[str, Position], db: Session, provider: MarketDataProvider
) -> list[str]:
    """Asigna precio actual; devuelve advertencias (sin lanzar) para no romper la vista."""
    warnings = []
    for pos in positions.values():
        if not pos.quantity:
            continue
        asset = db.get(Asset, pos.symbol)
        if asset and asset.manual_price is not None:
            pos.price = asset.manual_price
            pos.price_source = f"manual ({asset.manual_price_date or 's/f'})"
            continue
        try:
            q = provider.quote(pos.symbol)
            pos.price, pos.price_source = q.price, f"{provider.name} {q.as_of}"
        except ProviderError as exc:
            warnings.append(str(exc))
    return warnings


@dataclass
class Allocation:
    by_sector: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    by_country: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    by_type: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    by_symbol: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    total_usd: Decimal = ZERO


def allocation(positions: dict[str, Position], fx: FxConverter, today: date) -> Allocation:
    out = Allocation()
    for p in positions.values():
        mv = p.market_value
        if not mv:
            continue
        usd = fx.convert(mv, p.currency, "USD", today) if p.currency != "USD" else mv
        out.total_usd += usd
        out.by_sector[p.sector] += usd
        out.by_country[p.country] += usd
        out.by_type[p.asset_type] += usd
        out.by_symbol[p.symbol] += usd
    return out


def _price_on(bars: list[PriceBar], day: date) -> Decimal | None:
    days = [b.day for b in bars]
    idx = bisect.bisect_right(days, day) - 1
    return bars[idx].close if idx >= 0 else None


@dataclass(frozen=True)
class BenchmarkComparison:
    benchmark: str
    invested_net: Decimal
    portfolio_value: Decimal
    benchmark_value: Decimal
    series: list[dict[str, str]]
    excluded: list[str]

    @property
    def difference(self) -> Decimal:
        return self.portfolio_value - self.benchmark_value


def compare_with_benchmark(
    trades: list[Trade],
    provider: MarketDataProvider,
    today: date,
    benchmark: str = BENCHMARK,
    points: int = 60,
) -> BenchmarkComparison:
    """Solo considera activos en USD con historial de precios (los locales en CRC se excluyen
    y se informa)."""
    usd_trades = [t for t in trades if t.asset.currency == "USD" and t.asset.manual_price is None]
    excluded = sorted({t.symbol for t in trades} - {t.symbol for t in usd_trades})
    if not usd_trades:
        return BenchmarkComparison(benchmark, ZERO, ZERO, ZERO, [], excluded)
    start = usd_trades[0].trade_date - timedelta(days=7)
    bench = provider.history(benchmark, start, today)
    histories: dict[str, list[PriceBar]] = {}
    for sym in {t.symbol for t in usd_trades}:
        try:
            histories[sym] = provider.history(sym, start, today)
        except ProviderError:
            excluded.append(sym)
    usd_trades = [t for t in usd_trades if t.symbol in histories]

    step = max((today - usd_trades[0].trade_date).days // points, 1) if usd_trades else 1
    sample_days = [usd_trades[0].trade_date + timedelta(days=i * step) for i in range(points + 1)]
    sample_days = [d for d in sample_days if d <= today] + [today]

    qty: dict[str, Decimal] = defaultdict(lambda: ZERO)
    shadow = ZERO
    invested = ZERO
    series = []
    ti = 0
    for day in sample_days:
        while ti < len(usd_trades) and usd_trades[ti].trade_date <= day:
            t = usd_trades[ti]
            cash = t.quantity * t.price + (t.fees if t.side is TradeSide.BUY else -t.fees)
            bench_px = _price_on(bench, t.trade_date)
            sign = 1 if t.side is TradeSide.BUY else -1
            qty[t.symbol] += sign * t.quantity
            invested += sign * cash
            if bench_px:
                shadow += sign * cash / bench_px
            ti += 1
        port_val = sum((q * (_price_on(histories[s], day) or ZERO) for s, q in qty.items()), ZERO)
        bench_val = shadow * (_price_on(bench, day) or ZERO)
        series.append(
            {
                "date": day.isoformat(),
                "portfolio": str(port_val.quantize(Decimal("0.01"))),
                "benchmark": str(bench_val.quantize(Decimal("0.01"))),
                "invested": str(invested.quantize(Decimal("0.01"))),
            }
        )
    last = series[-1]
    return BenchmarkComparison(
        benchmark,
        invested.quantize(Decimal("0.01")),
        Decimal(last["portfolio"]),
        Decimal(last["benchmark"]),
        series,
        sorted(set(excluded)),
    )
