from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from moneytalk.investments.backtest import BacktestRequest, run_backtest
from moneytalk.investments.comparator import CompareRequest, OptionIn, compare
from moneytalk.investments.edgar import compute_official
from moneytalk.investments.reports import AiReportSummary, quarterly_changes, summarize_quarter
from moneytalk.investments.screener import Criterion
from tests import factories as f
from tests.fakes import FakeProvider, linear_history

# --- Comparador ---


def test_cdp_simple_interest_with_tax() -> None:
    req = CompareRequest(
        amount=Decimal("1000000"),
        months=12,
        fx_rate=Decimal("500"),
        inflation=Decimal("0.03"),
        options=[OptionIn(name="CDP 12m", currency="CRC", annual_rate=Decimal("0.06"))],
    )
    [row], _ = compare(req)
    assert row.gross_interest == Decimal("60000.00")
    assert row.tax == Decimal("9000.00")  # 15 %
    assert row.final_value_base == Decimal("1051000.00")
    assert row.net_annual_yield_base == Decimal("0.05100")
    assert row.real_annual_yield == pytest.approx(Decimal("0.0204"), abs=Decimal("0.0001"))


def test_usd_option_depends_on_exchange_rate_and_break_even() -> None:
    options = [
        OptionIn(name="CDP colones", currency="CRC", annual_rate=Decimal("0.06")),
        OptionIn(name="CDP dólares", currency="USD", annual_rate=Decimal("0.04")),
    ]
    base = {
        "amount": Decimal("1000000"),
        "months": 12,
        "fx_rate": Decimal("500"),
        "options": options,
    }
    flat, extra = compare(CompareRequest(**base))
    usd_flat = next(r for r in flat if r.currency == "USD")
    assert usd_flat.final_value == Decimal("2068.00")  # 2000 + 80 − 12
    # Punto de equilibrio: (1.051 / 1.034) − 1 ≈ 1.64 % de devaluación anual
    assert extra["break_even_depreciation"] == pytest.approx(
        Decimal("0.01644"), abs=Decimal("0.0001")
    )

    deval, _ = compare(CompareRequest(**base, colon_depreciation=Decimal("0.05")))
    usd = next(r for r in deval if r.currency == "USD")
    crc = next(r for r in deval if r.currency == "CRC")
    assert usd.final_value_base > crc.final_value_base


def test_compare_api_uses_stored_options(client: TestClient, db: Session) -> None:
    f.rate(db, date(2026, 10, 1), sell="510")
    opt = client.post(
        "/api/investments/fixed-income",
        json={
            "name": "CDP 6m",
            "institution": "BN",
            "currency": "CRC",
            "annual_rate": "0.055",
            "term_months": 6,
        },
    ).json()
    res = client.post(
        "/api/investments/compare",
        json={
            "amount": "500000",
            "months": 6,
            "option_ids": [opt["id"]],
            "extra_options": [
                {
                    "name": "Fondo USD",
                    "currency": "USD",
                    "annual_rate": "0.045",
                    "compounding": "monthly",
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["assumptions"]["fx_rate_start"] == "510.0000"
    assert {r["name"] for r in body["rows"]} == {"CDP 6m (BN)", "Fondo USD"}


# --- Backtesting ---


def _annual(val: float, fy: int, filed: str, accn: str, instant: bool = False) -> dict[str, Any]:
    e: dict[str, Any] = {
        "val": val,
        "end": f"{fy}-12-31",
        "form": "10-K",
        "fp": "FY",
        "accn": accn,
        "filed": filed,
    }
    if not instant:
        e["start"] = f"{fy}-01-01"
    return e


def _company(roe_by_year: dict[int, float], eps: float = 5.0) -> dict[str, Any]:
    revenue, ni, equity, epsl = [], [], [], []
    for fy, roe in roe_by_year.items():
        filed, accn = f"{fy + 1}-02-15", f"000-{fy + 1}"
        revenue.append(_annual(1000.0 * (1.1 ** (fy - 2019)), fy, filed, accn))
        ni.append(_annual(roe * 1000, fy, filed, accn))
        equity.append(_annual(1000.0, fy, filed, accn, instant=True))
        epsl.append(_annual(eps, fy, filed, accn))
    return {
        "entityName": "X",
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": revenue}},
                "NetIncomeLoss": {"units": {"USD": ni}},
                "StockholdersEquity": {"units": {"USD": equity}},
                "EarningsPerShareDiluted": {"units": {"USD/shares": epsl}},
            }
        },
    }


def test_point_in_time_uses_only_filed_reports() -> None:
    facts = _company({2020: 0.10, 2021: 0.30})
    assert compute_official("X", 1, facts, as_of=date(2021, 4, 1)).metrics["roe"] == pytest.approx(
        0.10
    )
    assert compute_official("X", 1, facts, as_of=date(2022, 4, 1)).metrics["roe"] == pytest.approx(
        0.30
    )


def test_backtest_selects_by_criteria_and_warns() -> None:
    today = date(2026, 10, 16)
    years = dict.fromkeys(range(2019, 2026), 0.25)
    facts = {"AAA": _company(years), "BBB": _company(dict.fromkeys(years, 0.05))}
    fake = FakeProvider()
    start = date(2020, 3, 1)
    fake.hist["AAA"] = linear_history(start, today, 100, 300)
    fake.hist["BBB"] = linear_history(start, today, 100, 100)
    fake.hist["SPY"] = linear_history(start, today, 300, 450)

    req = BacktestRequest(
        criteria=[
            Criterion(metric="roe", op=">=", value=0.15),
            Criterion(metric="pe", op="between", value=0, value_max=100),
            Criterion(metric="dividend_yield", op=">=", value=0.01),  # no reconstruible
        ],
        universe=["AAA", "BBB"],
        start_year=2021,
        end_year=2025,
    )
    res = run_backtest(req, fake, lambda s: (1, facts[s]), today)
    assert len(res.periods) == 5
    assert all(p.holdings == ["AAA"] for p in res.periods)
    first = res.periods[0]
    assert first.evidence["BBB"]["roe"] == pytest.approx(0.05)
    assert first.evidence["AAA"]["pe"] == pytest.approx(
        _price(fake, "AAA", first.start) / 5.0, rel=1e-3
    )
    assert res.stats["strategy"]["cagr"] > res.stats["universe"]["cagr"]  # type: ignore[operator]
    joined = " ".join(res.warnings)
    assert "supervivencia" in joined and "periodos anuales" in joined
    assert "no reconstruibles" in joined and res.unsupported_criteria
    assert res.curve[0]["strategy"] == 1.0


def _price(fake: FakeProvider, sym: str, day: date) -> float:
    return float(next(b.close for b in fake.hist[sym] if b.day == day))


def test_backtest_api_requires_valid_range(client: TestClient) -> None:
    from moneytalk.api import investments as inv_api
    from moneytalk.main import app

    app.dependency_overrides[inv_api.provider_dep] = FakeProvider
    try:
        res = client.post(
            "/api/investments/backtest",
            json={
                "criteria": [{"metric": "roe", "op": ">=", "value": 0.1}],
                "universe": ["A", "B"],
                "start_year": 2030,
                "end_year": 2031,
            },
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


# --- Reportes trimestrales ---


def _q(val: float, end: date, accn: str, instant: bool = False) -> dict[str, Any]:
    e: dict[str, Any] = {
        "val": val,
        "end": end.isoformat(),
        "form": "10-Q",
        "fp": "Q",
        "accn": accn,
    }
    if not instant:
        e["start"] = (end - timedelta(days=90)).isoformat()
    return e


def _quarterly_facts() -> dict[str, Any]:
    q = [date(2025, 6, 30), date(2026, 3, 31), date(2026, 6, 30)]
    rev = [_q(100, q[0], "a"), _q(110, q[1], "b"), _q(130, q[2], "c")]
    # Acumulado de 6 meses: debe ignorarse
    rev.append(
        {"val": 240, "end": "2026-06-30", "start": "2026-01-01", "form": "10-Q", "accn": "c"}
    )
    ni = [_q(10, q[0], "a"), _q(12, q[1], "b"), _q(9, q[2], "c")]
    return {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": rev}},
                "NetIncomeLoss": {"units": {"USD": ni}},
            }
        }
    }


def test_quarterly_changes_table() -> None:
    period, accn, rows = quarterly_changes(_quarterly_facts())
    assert period == date(2026, 6, 30) and accn == "c"
    rev = next(r for r in rows if r.metric == "revenue")
    assert rev.current == 130
    assert rev.qoq == pytest.approx(130 / 110 - 1)
    assert rev.yoy == pytest.approx(0.30)
    ni = next(r for r in rows if r.metric == "net_income")
    assert ni.yoy == pytest.approx(-0.10)


class _StubClaude:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def structured(self, *, system: str, prompt: str, schema: type, **_: object) -> AiReportSummary:
        self.prompts.append(prompt)
        assert "No des recomendaciones" in system
        return AiReportSummary(
            summary="Ingresos subieron 30 % interanual.", highlights=["a"], caveats=["b"]
        )


def test_summarize_quarter_is_cached(db: Session) -> None:
    stub = _StubClaude()
    first = summarize_quarter(db, "EJM", _quarterly_facts(), stub, "claude-opus-5-5")  # type: ignore[arg-type]
    assert first["summary"]["summary"].startswith("Ingresos")
    assert "+30.0%" in stub.prompts[0]
    second = summarize_quarter(db, "EJM", _quarterly_facts(), stub, "claude-opus-5-5")  # type: ignore[arg-type]
    assert second["cached"] is True and len(stub.prompts) == 1
    no_ai = summarize_quarter(db, "OTRA", _quarterly_facts(), None, "m")
    assert no_ai["summary"] is None and no_ai["table"]
