"""Proveedores con API key: Financial Modeling Prep y Alpha Vantage.

Quedan listos para activarse con `MARKET_PROVIDER=fmp|alphavantage`. Verificá los nombres
de campos contra la documentación vigente de cada servicio antes de depender de ellos: ambos
han cambiado endpoints en el pasado. Los planes gratuitos tienen límites diarios bajos;
la caché (TTL configurable) evita gastarlos.
"""

import time
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from moneytalk.investments.providers.base import (
    Fundamentals,
    PriceBar,
    ProviderError,
    Quote,
    to_float,
)


class _Throttled:
    min_interval: float = 0.0

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http or httpx.Client(timeout=20)
        self._last = 0.0

    def _get(self, url: str, params: dict[str, str]) -> Any:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            resp = self._http.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Sin URL en el mensaje: incluye la API key.
            raise ProviderError(f"{type(self).__name__}: {type(exc).__name__}") from exc
        return resp.json()


class FmpProvider(_Throttled):
    """Financial Modeling Prep (API "stable")."""

    name = "fmp"
    base = "https://financialmodelingprep.com/stable"
    min_interval = 0.3

    def __init__(self, api_key: str, http: httpx.Client | None = None) -> None:
        if not api_key:
            raise ProviderError("Falta FMP_API_KEY")
        super().__init__(http)
        self._key = api_key

    def _first(self, path: str, symbol: str) -> dict[str, Any]:
        data = self._get(f"{self.base}/{path}", {"symbol": symbol, "apikey": self._key})
        if not isinstance(data, list) or not data:
            raise ProviderError(f"FMP sin datos de {path} para {symbol}")
        first: dict[str, Any] = data[0]
        return first

    def quote(self, symbol: str) -> Quote:
        q = self._first("quote", symbol)
        return Quote(symbol, Decimal(str(q["price"])), "USD", date.today(), q.get("name"))  # noqa: DTZ011

    def fundamentals(self, symbol: str) -> Fundamentals:
        profile = self._first("profile", symbol)
        ratios = self._first("ratios-ttm", symbol)
        metrics = self._first("key-metrics-ttm", symbol)
        return Fundamentals(
            symbol=symbol,
            source=self.name,
            as_of=date.today(),  # noqa: DTZ011
            name=profile.get("companyName"),
            currency=profile.get("currency"),
            sector=profile.get("sector"),
            country=profile.get("country"),
            market_cap=to_float(profile.get("marketCap")),
            pe=to_float(ratios.get("priceToEarningsRatioTTM")),
            roe=to_float(metrics.get("returnOnEquityTTM")),
            debt_to_equity=to_float(ratios.get("debtToEquityRatioTTM")),
            fcf_yield=to_float(metrics.get("freeCashFlowYieldTTM")),
            gross_margin=to_float(ratios.get("grossProfitMarginTTM")),
            operating_margin=to_float(ratios.get("operatingProfitMarginTTM")),
            net_margin=to_float(ratios.get("netProfitMarginTTM")),
            dividend_yield=to_float(ratios.get("dividendYieldTTM")),
            payout_ratio=to_float(ratios.get("dividendPayoutRatioTTM")),
        )

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        data = self._get(
            f"{self.base}/historical-price-eod/dividend-adjusted",
            {
                "symbol": symbol,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "apikey": self._key,
            },
        )
        rows = data if isinstance(data, list) else data.get("historical", [])
        bars = [
            PriceBar(date.fromisoformat(r["date"]), Decimal(str(r.get("adjClose", r.get("close")))))
            for r in rows
        ]
        if not bars:
            raise ProviderError(f"FMP sin historial para {symbol}")
        return sorted(bars, key=lambda b: b.day)


class AlphaVantageProvider(_Throttled):
    name = "alphavantage"
    base = "https://www.alphavantage.co/query"
    min_interval = 12.0  # plan gratuito: pocas solicitudes por minuto

    def __init__(self, api_key: str, http: httpx.Client | None = None) -> None:
        if not api_key:
            raise ProviderError("Falta ALPHAVANTAGE_API_KEY")
        super().__init__(http)
        self._key = api_key

    def _call(self, function: str, **params: str) -> dict[str, Any]:
        data: dict[str, Any] = self._get(
            self.base, {"function": function, "apikey": self._key, **params}
        )
        if "Note" in data or "Information" in data:
            raise ProviderError("Alpha Vantage: límite de solicitudes alcanzado")
        return data

    def quote(self, symbol: str) -> Quote:
        q = self._call("GLOBAL_QUOTE", symbol=symbol).get("Global Quote", {})
        if not q.get("05. price"):
            raise ProviderError(f"Alpha Vantage sin cotización para {symbol}")
        return Quote(
            symbol, Decimal(q["05. price"]), "USD", date.fromisoformat(q["07. latest trading day"])
        )

    def fundamentals(self, symbol: str) -> Fundamentals:
        o = self._call("OVERVIEW", symbol=symbol)
        if not o.get("Symbol"):
            raise ProviderError(f"Alpha Vantage sin datos para {symbol}")
        return Fundamentals(
            symbol=symbol,
            source=self.name,
            as_of=date.today(),  # noqa: DTZ011
            name=o.get("Name"),
            currency=o.get("Currency"),
            sector=(o.get("Sector") or "").title() or None,
            country=o.get("Country"),
            market_cap=to_float(o.get("MarketCapitalization")),
            pe=to_float(o.get("TrailingPE") or o.get("PERatio")),
            roe=to_float(o.get("ReturnOnEquityTTM")),
            revenue_growth=to_float(o.get("QuarterlyRevenueGrowthYOY")),
            operating_margin=to_float(o.get("OperatingMarginTTM")),
            net_margin=to_float(o.get("ProfitMargin")),
            dividend_yield=to_float(o.get("DividendYield")),
        )

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        data = self._call("TIME_SERIES_DAILY", symbol=symbol, outputsize="full")
        series = data.get("Time Series (Daily)", {})
        bars = [
            PriceBar(date.fromisoformat(d), Decimal(v["4. close"]))
            for d, v in series.items()
            if start <= date.fromisoformat(d) <= end
        ]
        if not bars:
            raise ProviderError(f"Alpha Vantage sin historial para {symbol}")
        # Nota: TIME_SERIES_DAILY gratuito no está ajustado por dividendos.
        return sorted(bars, key=lambda b: b.day)
