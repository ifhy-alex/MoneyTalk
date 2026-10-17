from datetime import date, timedelta

from sqlalchemy.orm import Session

from moneytalk.investments.market import history, overview, summarize


def _series(start: date, days: int, p0: float, p1: float) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), p0 + (p1 - p0) * i / (days - 1)) for i in range(days)]


def test_summarize_trend_metrics() -> None:
    closes = _series(date(2025, 10, 1), 400, 100, 140)
    inst = summarize("X", "X", closes)
    assert inst is not None
    assert inst.above_sma50 and inst.above_sma200
    assert inst.from_52w_high is not None and abs(inst.from_52w_high) < 1e-9
    assert inst.change_1y is not None and inst.change_1y > 0
    assert len(inst.spark) == 66


def test_overview_is_cached_and_reports_missing(db: Session) -> None:
    calls: list[list[str]] = []

    def fake(symbols: list[str], start: date) -> dict[str, list[tuple[date, float]]]:
        calls.append(symbols)
        return {s: _series(date(2025, 9, 1), 420, 10, 12) for s in symbols if s != "^VIX"}

    today = date(2026, 10, 16)
    first = overview(db, today, download=fake)
    overview(db, today, download=fake)
    assert len(calls) == 1
    assert "^VIX" in first["missing"]
    titles = [g["title"] for g in first["groups"]]
    assert "ETFs amplios de bajo costo" in titles and "Empresas más grandes" in titles
    overview(db, today, download=fake, refresh=True)
    assert len(calls) == 2


def test_history_downsamples_long_ranges(db: Session) -> None:
    def fake(symbols: list[str], start: date) -> dict[str, list[tuple[date, float]]]:
        return {symbols[0]: _series(start, 1250, 50, 100)}

    h = history(db, "VOO", "5A", date(2026, 10, 16), download=fake)
    assert len(h["points"]) <= 400
    assert h["points"][-1]["close"] == 100
    assert abs(h["change"] - 1.0) < 1e-6
