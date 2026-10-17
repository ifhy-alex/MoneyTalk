"""Yahoo Finance vía `yfinance` (no oficial, sin API key).

Útil para empezar, pero Yahoo puede cambiar o limitar el acceso sin aviso y sus términos
restringen el uso a fines personales. Por eso todo pasa por la caché y la interfaz
permite cambiar a FMP o Alpha Vantage sin tocar el resto.

Normalización:
- `debtToEquity` viene en porcentaje (150.3) → se divide entre 100.
- El rendimiento por dividendo se calcula como dividendo anual / precio, porque el campo
  `dividendYield` de Yahoo ha cambiado de unidades entre versiones.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from moneytalk.investments.providers.base import (
    Fundamentals,
    PriceBar,
    ProviderError,
    Quote,
    to_float,
)


class YFinanceProvider:
    name = "yfinance"

    def _info(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        try:
            info: dict[str, Any] = yf.Ticker(symbol).info or {}
        except Exception as exc:  # yfinance lanza excepciones variadas
            raise ProviderError(f"yfinance no respondió para {symbol}: {exc}") from exc
        if not info or (
            info.get("regularMarketPrice") is None and info.get("currentPrice") is None
        ):
            raise ProviderError(f"Símbolo sin datos en Yahoo: {symbol}")
        return info

    def quote(self, symbol: str) -> Quote:
        info = self._info(symbol)
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return Quote(
            symbol=symbol,
            price=Decimal(str(price)),
            currency=str(info.get("currency") or "USD"),
            as_of=date.today(),  # noqa: DTZ011  fecha de consulta
            name=info.get("longName") or info.get("shortName"),
        )

    def fundamentals(self, symbol: str) -> Fundamentals:
        info = self._info(symbol)
        price = to_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        dividend = to_float(info.get("trailingAnnualDividendRate") or info.get("dividendRate"))
        fcf = to_float(info.get("freeCashflow"))
        mcap = to_float(info.get("marketCap"))
        dte = to_float(info.get("debtToEquity"))
        return Fundamentals(
            symbol=symbol,
            source=self.name,
            as_of=date.today(),  # noqa: DTZ011
            name=info.get("longName") or info.get("shortName"),
            currency=info.get("financialCurrency") or info.get("currency"),
            sector=info.get("sector"),
            country=info.get("country"),
            market_cap=mcap,
            pe=to_float(info.get("trailingPE")),
            roe=to_float(info.get("returnOnEquity")),
            debt_to_equity=dte / 100 if dte is not None else None,
            free_cash_flow=fcf,
            fcf_yield=fcf / mcap if fcf is not None and mcap else None,
            revenue_growth=to_float(info.get("revenueGrowth")),
            gross_margin=to_float(info.get("grossMargins")),
            operating_margin=to_float(info.get("operatingMargins")),
            net_margin=to_float(info.get("profitMargins")),
            dividend_yield=(dividend / price) if dividend is not None and price else 0.0,
            payout_ratio=to_float(info.get("payoutRatio")),
        )

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        import yfinance as yf

        try:
            df = yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
            )
        except Exception as exc:
            raise ProviderError(f"yfinance: sin historial para {symbol}: {exc}") from exc
        if df is None or df.empty:
            raise ProviderError(f"yfinance: sin historial para {symbol}")
        return [
            PriceBar(day=idx.date(), close=Decimal(str(round(float(row), 6))))
            for idx, row in df["Close"].items()
        ]
