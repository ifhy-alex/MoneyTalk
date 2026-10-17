import json
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.investments.providers import ProviderError, make_provider
from moneytalk.investments.providers.http_providers import AlphaVantageProvider, FmpProvider
from moneytalk.jobs import job_alerts
from moneytalk.models import Alert
from moneytalk.notifications.telegram import TelegramNotifier
from tests import factories as f


def _mock(routes: dict[str, Any]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.params.get("function") or request.url.path.rsplit("/", 1)[-1]
        assert "apikey" in request.url.params
        return httpx.Response(200, json=routes[key])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fmp_provider_maps_fields() -> None:
    http = _mock(
        {
            "profile": [
                {
                    "companyName": "Acme",
                    "currency": "USD",
                    "sector": "Tech",
                    "country": "US",
                    "marketCap": 1e9,
                }
            ],
            "ratios-ttm": [
                {
                    "priceToEarningsRatioTTM": 20,
                    "debtToEquityRatioTTM": 0.4,
                    "netProfitMarginTTM": 0.2,
                }
            ],
            "key-metrics-ttm": [{"returnOnEquityTTM": 0.3, "freeCashFlowYieldTTM": 0.05}],
            "quote": [{"price": 123.4, "name": "Acme"}],
            "dividend-adjusted": [
                {"date": "2026-10-15", "adjClose": 120},
                {"date": "2026-10-14", "adjClose": 119},
            ],
        }
    )
    p = FmpProvider("k", http=http)
    fnd = p.fundamentals("ACME")
    assert (fnd.pe, fnd.roe, fnd.debt_to_equity, fnd.fcf_yield) == (20.0, 0.3, 0.4, 0.05)
    assert str(p.quote("ACME").price) == "123.4"
    bars = p.history("ACME", date(2026, 10, 1), date(2026, 10, 16))
    assert [b.day.day for b in bars] == [14, 15]


def test_alphavantage_provider_and_rate_limit() -> None:
    p = AlphaVantageProvider(
        "k",
        http=_mock(
            {
                "OVERVIEW": {
                    "Symbol": "X",
                    "PERatio": "15.5",
                    "ReturnOnEquityTTM": "0.2",
                    "Sector": "TECHNOLOGY",
                    "DividendYield": "None",
                }
            }
        ),
    )
    p.min_interval = 0
    fnd = p.fundamentals("X")
    assert fnd.pe == 15.5 and fnd.sector == "Technology" and fnd.dividend_yield is None

    limited = AlphaVantageProvider("k", http=_mock({"GLOBAL_QUOTE": {"Note": "limit"}}))
    limited.min_interval = 0
    with pytest.raises(ProviderError, match="límite"):
        limited.quote("X")


def test_make_provider_validates_keys() -> None:
    assert make_provider(Settings(market_provider="yfinance")).name == "yfinance"
    with pytest.raises(ProviderError):
        make_provider(Settings(market_provider="fmp", fmp_api_key=""))
    with pytest.raises(ProviderError):
        make_provider(Settings(market_provider="otro"))


def test_scheduler_registers_jobs() -> None:
    from moneytalk import scheduler
    from moneytalk.config import get_settings

    get_settings.cache_clear()
    sched = scheduler.build_scheduler()
    ids = {j.id for j in sched.get_jobs()}
    assert {"ingest", "alerts", "weekly", "quotes"} <= ids


def test_job_alerts_notifies_once(db: Session) -> None:
    f.rate(db, date(2026, 6, 1))
    f.txn(db, date(2026, 10, 14), "-12.99", "NETFLIX", "USD", category_name="Suscripciones")
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(
        Settings(telegram_bot_token="t", telegram_chat_id="1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    settings = Settings(app_timezone="America/Costa_Rica")
    created = job_alerts(db, settings, notifier)
    assert created and len(sent) == len(created)
    job_alerts(db, settings, notifier)
    assert len(sent) == len(created)  # no reenvía
    assert all(a.notified_at for a in db.query(Alert).all())
