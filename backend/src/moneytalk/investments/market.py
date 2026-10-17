"""Panorama de mercado: índices, tasas, materias primas, sectores y tus posiciones.

Los datos vienen de Yahoo Finance (cotizaciones de EE. UU. con ~15 min de retraso) y se
cachean 15 minutos. Las "tendencias" son hechos medibles (rendimiento por periodo, precio
contra sus promedios móviles, distancia al máximo de 52 semanas), no pronósticos.
"""

import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.models import Asset, MarketCache

CACHE_TTL = timedelta(minutes=15)

GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Índices de EE. UU.",
        [
            ("^GSPC", "S&P 500"),
            ("^IXIC", "Nasdaq Composite"),
            ("^DJI", "Dow Jones"),
            ("^RUT", "Russell 2000"),
        ],
    ),
    (
        "Mundo",
        [
            ("^STOXX50E", "Euro Stoxx 50"),
            ("^FTSE", "FTSE 100 (Reino Unido)"),
            ("^N225", "Nikkei 225 (Japón)"),
            ("^HSI", "Hang Seng (Hong Kong)"),
        ],
    ),
    (
        "Riesgo, tasas y monedas",
        [
            ("^VIX", "Volatilidad (VIX)"),
            ("^TNX", "Bono EE. UU. 10 años (%)"),
            ("DX-Y.NYB", "Índice del dólar"),
            ("CRC=X", "USD/CRC (mercado)"),
        ],
    ),
    (
        "Materias primas y cripto",
        [("GC=F", "Oro"), ("CL=F", "Petróleo WTI"), ("BTC-USD", "Bitcoin")],
    ),
    (
        "ETFs amplios de bajo costo",
        [
            ("VOO", "Vanguard S&P 500"),
            ("VTI", "Vanguard Mercado Total EE. UU."),
            ("QQQ", "Invesco Nasdaq-100"),
            ("VXUS", "Vanguard Acciones Internacionales"),
            ("BND", "Vanguard Bonos Totales EE. UU."),
            ("SCHD", "Schwab Dividendos EE. UU."),
        ],
    ),
    (
        "Empresas más grandes",
        [
            ("NVDA", "NVIDIA"),
            ("MSFT", "Microsoft"),
            ("AAPL", "Apple"),
            ("AMZN", "Amazon"),
            ("GOOGL", "Alphabet (Google)"),
            ("META", "Meta Platforms"),
            ("BRK-B", "Berkshire Hathaway"),
            ("TSLA", "Tesla"),
        ],
    ),
    (
        "Sectores (ETF SPDR)",
        [
            ("XLK", "Tecnología"),
            ("XLC", "Comunicaciones"),
            ("XLY", "Consumo discrecional"),
            ("XLF", "Financiero"),
            ("XLV", "Salud"),
            ("XLI", "Industrial"),
            ("XLE", "Energía"),
            ("XLP", "Consumo básico"),
            ("XLU", "Servicios públicos"),
            ("XLB", "Materiales"),
            ("XLRE", "Bienes raíces"),
        ],
    ),
]

# Descarga: {símbolo: [(fecha, cierre), ...]} ordenado por fecha.
Downloader = Callable[[list[str], date], dict[str, list[tuple[date, float]]]]


def yahoo_download(symbols: list[str], start: date) -> dict[str, list[tuple[date, float]]]:
    import yfinance as yf

    df = yf.download(
        symbols,
        start=start.isoformat(),
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    out: dict[str, list[tuple[date, float]]] = {}
    for sym in symbols:
        try:
            closes = df[sym]["Close"].dropna()
        except KeyError:
            try:  # con un solo símbolo algunas versiones no agrupan por ticker
                col = df["Close"]
                closes = (col[sym] if hasattr(col, "columns") else col).dropna()
            except KeyError:
                continue
        out[sym] = [(idx.date(), float(v)) for idx, v in closes.items()]
    return out


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    last: float
    as_of: str
    change_1d: float | None
    change_1w: float | None
    change_1m: float | None
    change_3m: float | None
    change_ytd: float | None
    change_1y: float | None
    above_sma50: bool | None
    above_sma200: bool | None
    from_52w_high: float | None
    volatility_1m: float | None  # anualizada
    spark: list[float]


def _back(closes: list[tuple[date, float]], days: int) -> float | None:
    """Cierre más reciente con al menos `days` días calendario de antigüedad."""
    target = closes[-1][0] - timedelta(days=days)
    for d, v in reversed(closes):
        if d <= target:
            return v
    return None


def _chg(last: float, base: float | None) -> float | None:
    return (last / base - 1) if base else None


def summarize(symbol: str, name: str, closes: list[tuple[date, float]]) -> Instrument | None:
    if len(closes) < 2:
        return None
    last_day, last = closes[-1]
    values = [v for _, v in closes]
    ytd_base = next((v for d, v in reversed(closes) if d.year < last_day.year), None)
    sma50 = statistics.fmean(values[-50:]) if len(values) >= 50 else None
    sma200 = statistics.fmean(values[-200:]) if len(values) >= 200 else None
    year = [v for d, v in closes if d > last_day - timedelta(days=365)]
    rets = [b / a - 1 for a, b in zip(values[-22:-1], values[-21:], strict=False) if a]
    return Instrument(
        symbol=symbol,
        name=name,
        last=round(last, 4),
        as_of=last_day.isoformat(),
        change_1d=_chg(last, values[-2]),
        change_1w=_chg(last, _back(closes, 7)),
        change_1m=_chg(last, _back(closes, 30)),
        change_3m=_chg(last, _back(closes, 91)),
        change_ytd=_chg(last, ytd_base),
        change_1y=_chg(last, _back(closes, 365)),
        above_sma50=last > sma50 if sma50 else None,
        above_sma200=last > sma200 if sma200 else None,
        from_52w_high=(last / max(year) - 1) if year else None,
        volatility_1m=statistics.pstdev(rets) * (252**0.5) if len(rets) > 5 else None,
        spark=[round(v, 4) for v in values[-66:]],
    )


def overview(
    db: Session, today: date, download: Downloader = yahoo_download, refresh: bool = False
) -> dict[str, Any]:
    holdings = sorted(set(db.scalars(select(Asset.symbol).where(Asset.manual_price.is_(None)))))
    groups = [*GROUPS]
    if holdings:
        groups.append(("Tus posiciones", [(s, s) for s in holdings]))
    key = ",".join(holdings)

    row = db.scalar(
        select(MarketCache).where(
            MarketCache.provider == "yahoo",
            MarketCache.kind == "overview",
            MarketCache.symbol == "*",
            MarketCache.cache_key == key[:64],
        )
    )
    if row and not refresh and datetime.now(UTC) - row.fetched_at < CACHE_TTL:
        payload: dict[str, Any] = row.payload
        return payload

    symbols = [s for _, items in groups for s, _ in items]
    data = download(symbols, today - timedelta(days=400))
    result_groups = []
    missing = []
    for title, items in groups:
        rows = []
        for sym, name in items:
            inst = summarize(sym, name, data.get(sym, []))
            if inst:
                rows.append(asdict(inst))
            else:
                missing.append(sym)
        result_groups.append({"title": title, "items": rows})
    payload = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": "Yahoo Finance (≈15 min de retraso en EE. UU.; cierres ajustados)",
        "groups": result_groups,
        "missing": missing,
    }
    if row is None:
        row = MarketCache(provider="yahoo", kind="overview", symbol="*", cache_key=key[:64])
        db.add(row)
    row.payload = payload
    row.fetched_at = datetime.now(UTC)
    db.commit()
    return payload


RANGES: dict[str, int] = {"1M": 31, "3M": 92, "6M": 183, "1A": 366, "5A": 1830}


def history(
    db: Session, symbol: str, range_key: str, today: date, download: Downloader = yahoo_download
) -> dict[str, Any]:
    """Serie de cierres para el gráfico detallado de un instrumento (caché de 15 min)."""
    days = RANGES[range_key]
    key = f"{range_key}"
    row = db.scalar(
        select(MarketCache).where(
            MarketCache.provider == "yahoo",
            MarketCache.kind == "chart",
            MarketCache.symbol == symbol,
            MarketCache.cache_key == key,
        )
    )
    if row and datetime.now(UTC) - row.fetched_at < CACHE_TTL:
        cached: dict[str, Any] = row.payload
        return cached
    closes = download([symbol], today - timedelta(days=days)).get(symbol, [])
    if len(closes) > 400:  # ~1 punto por semana en 5 años
        step = len(closes) // 260 + 1
        closes = closes[::step] + ([closes[-1]] if (len(closes) - 1) % step else [])
    payload = {
        "symbol": symbol,
        "range": range_key,
        "points": [{"date": d.isoformat(), "close": round(v, 4)} for d, v in closes],
        "change": (closes[-1][1] / closes[0][1] - 1) if len(closes) > 1 and closes[0][1] else None,
    }
    if row is None:
        row = MarketCache(provider="yahoo", kind="chart", symbol=symbol, cache_key=key)
        db.add(row)
    row.payload = payload
    row.fetched_at = datetime.now(UTC)
    db.commit()
    return payload
