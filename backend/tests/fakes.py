from datetime import date, timedelta
from decimal import Decimal

from moneytalk.investments.providers.base import Fundamentals, PriceBar, ProviderError, Quote


def linear_history(start: date, end: date, p0: float, p1: float) -> list[PriceBar]:
    days = (end - start).days or 1
    return [
        PriceBar(start + timedelta(days=i), Decimal(str(round(p0 + (p1 - p0) * i / days, 4))))
        for i in range(days + 1)
    ]


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.fund: dict[str, Fundamentals] = {}
        self.prices: dict[str, Decimal] = {}
        self.hist: dict[str, list[PriceBar]] = {}
        self.calls: list[tuple[str, str]] = []

    def quote(self, symbol: str) -> Quote:
        self.calls.append(("quote", symbol))
        if symbol not in self.prices:
            raise ProviderError(f"sin precio {symbol}")
        return Quote(symbol, self.prices[symbol], "USD", date(2026, 10, 16), symbol)

    def fundamentals(self, symbol: str) -> Fundamentals:
        self.calls.append(("fundamentals", symbol))
        if symbol not in self.fund:
            raise ProviderError(f"sin datos {symbol}")
        return self.fund[symbol]

    def history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        self.calls.append(("history", symbol))
        if symbol not in self.hist:
            raise ProviderError(f"sin historial {symbol}")
        return [b for b in self.hist[symbol] if start <= b.day <= end]


def fundamentals(symbol: str, **kw: object) -> Fundamentals:
    base: dict[str, object] = {
        "symbol": symbol,
        "source": "fake",
        "as_of": date(2026, 10, 16),
        "name": f"{symbol} Inc",
        "currency": "USD",
        "sector": "Technology",
        "country": "United States",
        "market_cap": 1e12,
    }
    base.update(kw)
    return Fundamentals(**base)  # type: ignore[arg-type]
