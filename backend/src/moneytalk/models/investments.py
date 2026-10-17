import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneytalk.models.base import Base, CurrencyCode, str_enum


class MarketCache(Base):
    """Respuestas cacheadas de proveedores de mercado (respeta límites de cada API)."""

    __tablename__ = "market_cache"
    __table_args__ = (UniqueConstraint("provider", "kind", "symbol", "cache_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))  # quote | fundamentals | history | edgar
    symbol: Mapped[str] = mapped_column(String(32))
    cache_key: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[Any] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetType(enum.StrEnum):
    STOCK = "stock"
    ETF = "etf"
    BOND = "bond"
    FUND = "fund"
    CDP = "cdp"
    OTHER = "other"


class Asset(Base):
    __tablename__ = "assets"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    asset_type: Mapped[AssetType] = mapped_column(
        str_enum(AssetType, "asset_type"), default=AssetType.STOCK
    )
    currency: Mapped[CurrencyCode]
    sector: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(80))
    # Para activos sin cotización pública (fondos locales, CDP): precio que ingresás vos.
    manual_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    manual_price_date: Mapped[date | None] = mapped_column(Date)


class TradeSide(enum.StrEnum):
    BUY = "buy"
    SELL = "sell"


class Trade(Base):
    """Registro manual de compras/ventas. Las posiciones se derivan de aquí."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol", ondelete="CASCADE"), index=True)
    trade_date: Mapped[date] = mapped_column(Date)
    side: Mapped[TradeSide] = mapped_column(str_enum(TradeSide, "trade_side"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    fees: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    broker: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship()


class ScreenerPreset(Base):
    __tablename__ = "screener_presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    universe: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
