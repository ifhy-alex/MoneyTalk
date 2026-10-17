from datetime import timedelta

from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.investments.providers.base import (
    Fundamentals,
    MarketDataProvider,
    PriceBar,
    ProviderError,
    Quote,
)
from moneytalk.investments.providers.cache import CachedProvider
from moneytalk.investments.providers.http_providers import AlphaVantageProvider, FmpProvider
from moneytalk.investments.providers.yfinance_provider import YFinanceProvider


def make_provider(settings: Settings) -> MarketDataProvider:
    match settings.market_provider:
        case "yfinance":
            return YFinanceProvider()
        case "fmp":
            return FmpProvider(settings.fmp_api_key)
        case "alphavantage":
            return AlphaVantageProvider(settings.alphavantage_api_key)
        case other:
            raise ProviderError(f"Proveedor desconocido: {other}")


def cached_provider(db: Session, settings: Settings) -> CachedProvider:
    return CachedProvider(
        make_provider(settings), db, timedelta(hours=settings.market_cache_ttl_hours)
    )


__all__ = [
    "AlphaVantageProvider",
    "CachedProvider",
    "FmpProvider",
    "Fundamentals",
    "MarketDataProvider",
    "PriceBar",
    "ProviderError",
    "Quote",
    "YFinanceProvider",
    "cached_provider",
    "make_provider",
]
