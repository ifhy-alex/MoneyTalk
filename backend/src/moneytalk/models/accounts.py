import enum

from sqlalchemy import CHAR, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from moneytalk.models.base import Base, CurrencyCode, TimestampMixin, str_enum


class AccountKind(enum.StrEnum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    SAVINGS = "savings"
    CHECKING = "checking"


class Account(TimestampMixin, Base):
    """Una tarjeta o cuenta bancaria. Solo se guardan los últimos 4 dígitos.

    La moneda no forma parte de la identidad: las tarjetas de crédito en CR son bimoneda
    (CRC y USD con el mismo número). Cada transacción guarda su propia moneda.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("last4 ~ '^[0-9]{4}$'", name="last4_four_digits"),
        UniqueConstraint("institution", "kind", "last4"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    institution: Mapped[str] = mapped_column(String(32))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind, "account_kind"))
    last4: Mapped[str] = mapped_column(CHAR(4))
    currency: Mapped[CurrencyCode]  # moneda principal (la primera vista)
    nickname: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)
