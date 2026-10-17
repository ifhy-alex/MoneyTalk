from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from moneytalk.ai import ClaudeClient

NO_CATEGORY = "NINGUNA"

SYSTEM = (
    "Clasificás transacciones de tarjetas y cuentas de una persona en Costa Rica. "
    "Elegí exactamente una categoría de la lista dada, o NINGUNA si no hay evidencia "
    "suficiente. Usá tu conocimiento de comercios costarricenses e internacionales. "
    "La razón debe ser breve, en español."
)


class AiSuggestion(BaseModel):
    category: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class AiCategorizer(Protocol):
    def suggest(
        self, merchant: str, amount: Decimal, currency: str, categories: list[str]
    ) -> AiSuggestion | None: ...


class ClaudeCategorizer:
    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def suggest(
        self, merchant: str, amount: Decimal, currency: str, categories: list[str]
    ) -> AiSuggestion | None:
        direction = "salida" if amount < 0 else "entrada"
        prompt = (
            f"Comercio: {merchant}\nMonto: {abs(amount)} {currency} ({direction} de dinero)\n"
            f"Categorías: {', '.join(categories)}"
        )
        result = self._client.structured(system=SYSTEM, prompt=prompt, schema=AiSuggestion)
        if result is None or result.category.upper() == NO_CATEGORY:
            return None
        if result.category not in categories:
            return None  # no aceptamos categorías inventadas
        return result
