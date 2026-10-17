import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneytalk.models.base import Base, CurrencyCode, Money, str_enum
from moneytalk.models.categories import Category


class ExchangeRate(Base):
    """Tipo de cambio de referencia del BCCR (colones por dólar)."""

    __tablename__ = "exchange_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    buy: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    sell: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    source: Mapped[str] = mapped_column(String(16), default="BCCR")


class Budget(Base):
    """Presupuesto mensual por categoría. `month` NULL = aplica a todos los meses;
    un registro con `month` concreto lo sobrescribe para ese mes."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", name="uq_budgets_category_month"),
        Index(
            "uq_budgets_category_default",
            "category_id",
            unique=True,
            postgresql_where=text("month IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    month: Mapped[date | None] = mapped_column(Date)  # primer día del mes
    amount: Mapped[Money]
    currency: Mapped[CurrencyCode]

    category: Mapped[Category] = relationship()


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        # Solo puede haber un fondo de emergencia.
        Index(
            "uq_goals_single_emergency_fund",
            "is_emergency_fund",
            unique=True,
            postgresql_where=text("is_emergency_fund"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[Money]
    currency: Mapped[CurrencyCode]
    target_date: Mapped[date | None] = mapped_column(Date)
    monthly_contribution: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    priority: Mapped[int] = mapped_column(default=100)
    is_emergency_fund: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contributions: Mapped[list["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="GoalContribution.date"
    )


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Money]  # en la moneda de la meta; negativo = retiro
    note: Mapped[str | None] = mapped_column(String(200))

    goal: Mapped[Goal] = relationship(back_populates="contributions")


class AlertKind(enum.StrEnum):
    UNUSUAL_SPEND = "unusual_spend"
    BUDGET_NEAR_LIMIT = "budget_near_limit"
    BUDGET_EXCEEDED = "budget_exceeded"
    NEW_SUBSCRIPTION = "new_subscription"
    DUPLICATE_SUBSCRIPTION = "duplicate_subscription"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[AlertKind] = mapped_column(str_enum(AlertKind, "alert_kind"))
    # Evita repetir la misma alerta (p. ej. "presupuesto 80 %" una sola vez por mes).
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True)
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSetting(Base):
    """Preferencias editables (umbrales, meses de fondo de emergencia, etc.)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
