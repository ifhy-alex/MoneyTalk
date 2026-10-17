"""Cliente de Claude compartido.

Solo se usa para lo que las reglas no resuelven (categorización dudosa, resúmenes). Nunca
se envían números de tarjeta/cuenta: solo comercio, monto, moneda y textos de reportes.

`fallbacks="default"`: si el modelo principal declina una solicitud (stop_reason
"refusal"), el servidor reintenta en un modelo alternativo elegido por categoría.
"""

import logging
from typing import Literal, TypeVar

import anthropic
from anthropic.types.beta import BetaOutputConfigParam
from pydantic import BaseModel

from moneytalk.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high", "xhigh", "max"]

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeClient:
    def __init__(self, settings: Settings) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2)
        self._model = settings.claude_model

    def structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        effort: Effort = "low",
        max_tokens: int = 2048,
    ) -> T | None:
        """Respuesta validada contra `schema`, o None si falla/declina (el llamador decide)."""
        output_config: BetaOutputConfigParam = {"effort": effort}
        try:
            response = self._client.beta.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError:
            log.warning("Claude: límite de tasa alcanzado")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("Claude: error HTTP %s", exc.status_code)
            return None
        except anthropic.APIConnectionError:
            log.warning("Claude: sin conexión")
            return None
        if response.stop_reason in {"refusal", "max_tokens"}:
            log.info("Claude no completó la respuesta: %s", response.stop_reason)
            return None
        return response.parsed_output


def claude_from_settings(settings: Settings) -> ClaudeClient | None:
    return ClaudeClient(settings) if settings.anthropic_api_key else None
