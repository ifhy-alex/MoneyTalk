from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from moneytalk.models.accounts import AccountKind


@dataclass(frozen=True)
class EmailMessage:
    """Correo ya decodificado, independiente de Gmail (facilita pruebas y otros proveedores)."""

    message_id: str
    sender: str
    subject: str
    received_at: datetime | None
    body_text: str


@dataclass(frozen=True)
class ParsedTransaction:
    """Salida común de todos los parsers. Monto con signo: negativo = salida de dinero."""

    institution: str
    account_kind: AccountKind
    last4: str
    txn_date: date
    amount: Decimal
    currency: str
    merchant: str
    occurred_at: datetime | None = None
    reference: str | None = None  # número de autorización/referencia del banco
    line_no: int = 0
    extra: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.last4) != 4 or not self.last4.isdigit():
            raise ValueError("last4 debe tener exactamente 4 dígitos")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError(f"moneda no soportada: {self.currency}")

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["txn_date"] = self.txn_date.isoformat()
        data["occurred_at"] = self.occurred_at.isoformat() if self.occurred_at else None
        data["amount"] = str(self.amount)
        data["account_kind"] = self.account_kind.value
        return data
