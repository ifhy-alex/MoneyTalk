"""Importa todos los modelos para que Alembic y `Base.metadata` los vean."""

from moneytalk.models.accounts import Account, AccountKind
from moneytalk.models.base import Base, Currency
from moneytalk.models.categories import Category, CategoryKind, CategoryRule, MatchType
from moneytalk.models.finance import (
    Alert,
    AlertKind,
    AppSetting,
    Budget,
    ExchangeRate,
    Goal,
    GoalContribution,
)
from moneytalk.models.ingestion import RawDocument, RawDocumentStatus, SourceType
from moneytalk.models.investments import (
    Asset,
    AssetType,
    MarketCache,
    ScreenerPreset,
    Trade,
    TradeSide,
)
from moneytalk.models.transactions import (
    CategorySource,
    CategoryStatus,
    Transaction,
    TransactionSource,
)

__all__ = [
    "Account",
    "AccountKind",
    "Alert",
    "AlertKind",
    "AppSetting",
    "Asset",
    "AssetType",
    "Base",
    "Budget",
    "Category",
    "CategoryKind",
    "CategoryRule",
    "CategorySource",
    "CategoryStatus",
    "Currency",
    "ExchangeRate",
    "Goal",
    "GoalContribution",
    "MarketCache",
    "MatchType",
    "RawDocument",
    "RawDocumentStatus",
    "ScreenerPreset",
    "SourceType",
    "Trade",
    "TradeSide",
    "Transaction",
    "TransactionSource",
]
