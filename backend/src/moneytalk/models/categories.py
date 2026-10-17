import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneytalk.models.base import Base, str_enum


class CategoryKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("parent_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    kind: Mapped[CategoryKind] = mapped_column(
        str_enum(CategoryKind, "category_kind"), default=CategoryKind.EXPENSE
    )
    # Marca categorías como "Suscripciones" para detectar cargos recurrentes nuevos/duplicados.
    is_subscription: Mapped[bool] = mapped_column(default=False)


class MatchType(enum.StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"


class CategoryRule(Base):
    """Regla comercio → categoría. Se evalúan por prioridad descendente; gana la primera."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_type: Mapped[MatchType] = mapped_column(str_enum(MatchType, "match_type"))
    pattern: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(default=100)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_from_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[Category] = relationship()
