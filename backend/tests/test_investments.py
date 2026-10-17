from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from moneytalk.api import investments as inv_api
from moneytalk.finance.fx import FxConverter
from moneytalk.investments.available import available_to_invest
from moneytalk.investments.edgar import EdgarClient, compute_official
from moneytalk.investments.portfolio import build_positions, compare_with_benchmark, load_trades
from moneytalk.investments.providers.cache import CachedProvider
from moneytalk.investments.providers.yfinance_provider import YFinanceProvider
from moneytalk.investments.screener import Criterion, screen_one
from moneytalk.main import app
from moneytalk.models import Asset, Goal, GoalContribution, Trade, TradeSide
from tests import factories as f
from tests.fakes import FakeProvider, fundamentals, linear_history


def _fact(
    val: float, end: str, start: str | None = None, accn: str = "0001-26-000001"
) -> dict[str, Any]:
    entry: dict[str, Any] = {"val": val, "end": end, "form": "10-K", "fp": "FY", "accn": accn}
    if start:
        entry["start"] = start
    return entry


def _facts() -> dict[str, Any]:
    def flow(v24: float, v25: float) -> dict[str, Any]:
        return {
            "units": {
                "USD": [
                    _fact(v24, "2024-12-31", "2024-01-01", "0001-25-000001"),
                    _fact(v25, "2025-12-31", "2025-01-01"),
                    # Trimestre dentro del 10-K: debe ignorarse
                    _fact(v25 / 4, "2025-12-31", "2025-10-01"),
                ]
            }
        }

    def instant(v: float) -> dict[str, Any]:
        return {"units": {"USD": [_fact(v, "2025-12-31")]}}

    return {
        "entityName": "Ejemplo Corp",
        "facts": {
            "us-gaap": {
                "Revenues": flow(1000.0, 1100.0),
                "NetIncomeLoss": flow(150.0, 165.0),
                "GrossProfit": flow(400.0, 440.0),
                "StockholdersEquity": instant(1000.0),
                "LongTermDebtNoncurrent": instant(500.0),
                "NetCashProvidedByUsedInOperatingActivities": flow(200.0, 240.0),
                "PaymentsToAcquirePropertyPlantAndEquipment": flow(50.0, 60.0),
            }
        },
    }


def test_compute_official_from_sec_facts() -> None:
    off = compute_official("EJM", 123, _facts())
    assert off.fiscal_year == 2025
    assert off.metrics["roe"] == pytest.approx(0.165)
    assert off.metrics["debt_to_equity"] == pytest.approx(0.5)
    assert off.metrics["free_cash_flow"] == pytest.approx(180.0)
    assert off.metrics["revenue_growth"] == pytest.approx(0.10)
    assert off.metrics["gross_margin"] == pytest.approx(0.4)
    assert "10-K FY2025" in off.provenance["roe"] and "NetIncomeLoss" in off.provenance["roe"]


def test_edgar_client_user_agent_and_cache(db: Session) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "company_tickers" in str(request.url):
            return httpx.Response(
                200, json={"0": {"cik_str": 123, "ticker": "EJM", "title": "Ejemplo"}}
            )
        return httpx.Response(200, json=_facts())

    http = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": "MT a@b.com"}
    )
    client = EdgarClient(db, "MT a@b.com", http=http)
    assert client.official("EJM").fiscal_year == 2025
    assert client.official("ejm").fiscal_year == 2025
    assert len(calls) == 2  # segunda consulta sale de la caché
    assert calls[1].url.path.endswith("CIK0000000123.json")
    assert calls[0].headers["User-Agent"] == "MT a@b.com"


def test_screener_reports_evidence_and_missing_data() -> None:
    criteria = [
        Criterion(metric="pe", op="between", value=0, value_max=25),
        Criterion(metric="roe", op=">=", value=0.15),
        Criterion(metric="dividend_yield", op=">=", value=0.02),
    ]
    good = screen_one("AAA", criteria, fundamentals("AAA", pe=18.0, roe=0.3, dividend_yield=None))
    assert (good.passed, good.failed, good.missing) == (2, 0, 1)
    assert not good.meets_all
    missing = next(r for r in good.results if r.metric == "dividend_yield")
    assert missing.passed is None and missing.source == "sin dato"

    loss = screen_one("BBB", criteria[:1], fundamentals("BBB", pe=-5.0))
    assert loss.results[0].passed is False  # P/E negativo no "cumple" un P/E bajo


def test_screener_prefers_sec_values() -> None:
    off = compute_official("EJM", 1, _facts())
    r = screen_one(
        "EJM",
        [Criterion(metric="roe", op=">=", value=0.2)],
        fundamentals("EJM", roe=0.25),
        off,
    )
    assert r.results[0].actual == pytest.approx(0.165)
    assert r.results[0].passed is False
    assert "SEC" in r.results[0].source


def test_between_requires_max() -> None:
    with pytest.raises(ValueError, match="value_max"):
        Criterion(metric="pe", op="between", value=10)


def test_yfinance_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.info = {
                "currentPrice": 200.0,
                "trailingPE": 30.0,
                "returnOnEquity": 1.5,
                "debtToEquity": 150.0,
                "freeCashflow": 1e11,
                "marketCap": 3e12,
                "trailingAnnualDividendRate": 1.0,
                "dividendYield": 0.5,  # unidades ambiguas: se ignora
                "sector": "Technology",
                "country": "United States",
                "currency": "USD",
            }

    import yfinance

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    fnd = YFinanceProvider().fundamentals("AAPL")
    assert fnd.debt_to_equity == pytest.approx(1.5)
    assert fnd.dividend_yield == pytest.approx(0.005)
    assert fnd.fcf_yield == pytest.approx(1e11 / 3e12)


def test_cached_provider_avoids_repeat_calls(db: Session) -> None:
    fake = FakeProvider()
    fake.fund["AAA"] = fundamentals("AAA", pe=10.0)
    fake.hist["AAA"] = linear_history(date(2026, 1, 1), date(2026, 10, 16), 100, 150)
    cached = CachedProvider(fake, db, timedelta(hours=12))
    assert cached.fundamentals("AAA").pe == 10.0
    assert cached.fundamentals("AAA").pe == 10.0
    h1 = cached.history("AAA", date(2026, 3, 1), date(2026, 6, 1))
    h2 = cached.history("AAA", date(2026, 4, 1), date(2026, 5, 1))
    assert h1[0].day == date(2026, 3, 1) and h2[0].day == date(2026, 4, 1)
    assert fake.calls.count(("fundamentals", "AAA")) == 1
    assert fake.calls.count(("history", "AAA")) == 1


def _seed_trades(db: Session) -> None:
    db.add(Asset(symbol="AAA", currency="USD", sector="Technology", country="United States"))
    db.add(Asset(symbol="CDP-BN", currency="CRC", asset_type="cdp", manual_price=Decimal("1")))
    db.flush()
    db.add_all(
        [
            Trade(
                symbol="AAA",
                trade_date=date(2026, 1, 2),
                side=TradeSide.BUY,
                quantity=Decimal(10),
                price=Decimal(100),
                fees=Decimal(5),
            ),
            Trade(
                symbol="AAA",
                trade_date=date(2026, 3, 2),
                side=TradeSide.BUY,
                quantity=Decimal(10),
                price=Decimal(120),
            ),
            Trade(
                symbol="AAA",
                trade_date=date(2026, 6, 1),
                side=TradeSide.SELL,
                quantity=Decimal(5),
                price=Decimal(140),
                fees=Decimal(5),
            ),
            Trade(
                symbol="CDP-BN",
                trade_date=date(2026, 2, 1),
                side=TradeSide.BUY,
                quantity=Decimal(500000),
                price=Decimal(1),
            ),
        ]
    )
    db.flush()


def test_positions_average_cost_and_realized(db: Session) -> None:
    _seed_trades(db)
    pos = build_positions(load_trades(db))["AAA"]
    assert pos.quantity == 15
    # costo: 1005 + 1200 = 2205 → prom 110.25; venta 5 → realiza 700-5-551.25
    assert pos.realized_pnl == Decimal("143.75")
    assert pos.cost_basis == Decimal("1653.75")


def test_benchmark_shadow_portfolio(db: Session) -> None:
    _seed_trades(db)
    fake = FakeProvider()
    today = date(2026, 10, 16)
    fake.hist["AAA"] = linear_history(date(2025, 12, 20), today, 100, 160)
    fake.hist["SPY"] = linear_history(date(2025, 12, 20), today, 500, 550)
    cmp = compare_with_benchmark(load_trades(db), fake, today)
    assert "CDP-BN" in cmp.excluded
    assert cmp.portfolio_value > cmp.benchmark_value  # AAA subió 60 %, SPY 10 %
    assert cmp.series[-1]["date"] == today.isoformat()


def test_available_to_invest_waits_for_emergency_fund(db: Session) -> None:
    f.rate(db, date(2026, 6, 1))
    for m in (7, 8, 9):
        f.txn(db, date(2026, m, 1), "1000000", "PLANILLA", category_name="Salario")
        f.txn(db, date(2026, m, 5), "-600000", "ALQUILER", category_name="Hogar")
    today = date(2026, 10, 16)
    assert available_to_invest(db, FxConverter(db), today).available_monthly == 0  # sin fondo

    goal = Goal(
        name="Fondo",
        target_amount=Decimal("1200000"),
        currency="CRC",
        is_emergency_fund=True,
        monthly_contribution=Decimal("100000"),
    )
    db.add(goal)
    db.flush()
    res = available_to_invest(db, FxConverter(db), today)
    assert res.surplus == Decimal("300000.00")
    assert res.available_monthly == 0 and res.emergency_fund_months_left == 4

    db.add(GoalContribution(goal_id=goal.id, date=today, amount=Decimal("1200000")))
    db.flush()
    db.expire_all()
    res = available_to_invest(db, FxConverter(db), today)
    assert res.available_monthly == Decimal("400000.00")  # ya no hay aporte pendiente al fondo


def test_investments_api(client: TestClient, db: Session) -> None:
    fake = FakeProvider()
    fake.fund["AAA"] = fundamentals("AAA", pe=15.0, roe=0.2, debt_to_equity=0.5)
    fake.fund["BBB"] = fundamentals("BBB", pe=40.0, roe=0.05, sector="Energy", country="Canada")
    fake.prices = {"AAA": Decimal("130"), "BBB": Decimal("50")}
    app.dependency_overrides[inv_api.provider_dep] = lambda: CachedProvider(
        fake, db, timedelta(hours=1)
    )
    try:
        presets = client.get("/api/investments/screener/presets").json()
        assert len(presets) == 2

        res = client.post(
            "/api/investments/screener/run",
            json={
                "criteria": [
                    {"metric": "pe", "op": "<=", "value": 20},
                    {"metric": "roe", "op": ">=", "value": 0.15},
                ],
                "universe": ["bbb", "AAA", "ZZZ"],
                "use_sec": False,
            },
        ).json()
        assert "asesoría" in res["disclaimer"]
        assert [r["symbol"] for r in res["rows"]] == ["AAA", "BBB", "ZZZ"]
        assert res["rows"][0]["meets_all"] is True
        assert res["rows"][2]["error"]

        for body in (
            {
                "symbol": "AAA",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": "10",
                "price": "100",
            },
            {
                "symbol": "BBB",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": "20",
                "price": "50",
            },
        ):
            assert client.post("/api/investments/trades", json=body).status_code == 201
        too_much = {
            "symbol": "AAA",
            "trade_date": "2026-02-01",
            "side": "sell",
            "quantity": "99",
            "price": "1",
        }
        assert client.post("/api/investments/trades", json=too_much).status_code == 422

        port = client.get("/api/investments/portfolio").json()
        aaa = next(p for p in port["positions"] if p["symbol"] == "AAA")
        assert Decimal(aaa["market_value"]) == Decimal("1300.00")
        assert aaa["unrealized_pct"] == pytest.approx(0.3)
        assert port["by_sector"]["Technology"] == pytest.approx(1300 / 2300)
        assert port["by_country"]["Canada"] == pytest.approx(1000 / 2300)
    finally:
        app.dependency_overrides.pop(inv_api.provider_dep, None)
