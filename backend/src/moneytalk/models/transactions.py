import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneytalk.models.accounts import Account
from moneytalk.models.base import Base, CurrencyCode, Money, TimestampMixin, str_enum
from moneytalk.models.categories import Category
from moneytalk.models.ingestion import RawDocument


class CategoryStatus(enum.StrEnum):
    UNCATEGORIZED = "uncategorized"
    SUGGESTED = "suggested"  # sugerida por IA, pendiente de confirmar
    CONFIRMED = "confirmed"


class CategorySource(enum.StrEnum):
    RULE = "rule"
    AI = "ai"
    MANUAL = "manual"


class Transaction(TimestampMixin, Base):
    """Transacción canónica. Monto con signo: negativo = salida de dinero."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_dedup", "account_id", "txn_date", "amount"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    txn_date: Mapped[date] = mapped_column(Date, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Money]
    currency: Mapped[CurrencyCode]
    merchant_raw: Mapped[str] = mapped_column(String(255))
    merchant_normalized: Mapped[str] = mapped_column(String(255), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    category_status: Mapped[CategoryStatus] = mapped_column(
        str_enum(CategoryStatus, "category_status"), default=CategoryStatus.UNCATEGORIZED
    )
    category_source: Mapped[CategorySource | None] = mapped_column(
        str_enum(CategorySource, "category_source")
    )
    ai_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    account: Mapped[Account] = relationship()
    category: Mapped[Category | None] = relationship()
    sources: Mapped[list["TransactionSource"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class TransactionSource(Base):
    """Una observación de la transacción (un correo o una línea de un estado de cuenta)."""

    __tablename__ = "transaction_sources"
    __table_args__ = (UniqueConstraint("raw_document_id", "line_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    raw_document_id: Mapped[int] = mapped_column(
        ForeignKey("raw_documents.id", ondelete="CASCADE"), index=True
    )
    # Un PDF genera muchas transacciones: line_no distingue cada línea del mismo documento.
    line_no: Mapped[int] = mapped_column(default=0)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB)
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.00"))

    transaction: Mapped[Transaction] = relationship(back_populates="sources")
    raw_document: Mapped[RawDocument] = relationship()
