import enum
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import CHAR, DateTime, Enum, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de constraints deterministas: Alembic puede generar y revertir migraciones limpias.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Money = Annotated[Decimal, mapped_column(Numeric(14, 2))]
CurrencyCode = Annotated[str, mapped_column(CHAR(3))]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def str_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """Enum guardado como VARCHAR + CHECK.

    Los ENUM nativos de Postgres obligan a migraciones especiales para agregar valores;
    un CHECK se reemplaza en una migración normal.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Currency(enum.StrEnum):
    CRC = "CRC"
    USD = "USD"
