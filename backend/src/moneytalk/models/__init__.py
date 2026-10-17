"""Importa todos los modelos para que Alembic y `Base.metadata` los vean."""

from moneytalk.models.accounts import Account, AccountKind
from moneytalk.models.base import Base, Currency
from moneytalk.models.categories import Category, CategoryKind, CategoryRule, MatchType
from moneytalk.models.ingestion import RawDocument, RawDocumentStatus, SourceType
from moneytalk.models.transactions import (
    CategorySource,
    CategoryStatus,
    Transaction,
    TransactionSource,
)

__all__ = [
    "Account",
    "AccountKind",
    "Base",
    "Category",
    "CategoryKind",
    "CategoryRule",
    "CategorySource",
    "CategoryStatus",
    "Currency",
    "MatchType",
    "RawDocument",
    "RawDocumentStatus",
    "SourceType",
    "Transaction",
    "TransactionSource",
]
