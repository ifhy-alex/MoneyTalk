"""Logging con filtro de datos personales.

Los correos y estados de cuenta contienen números de tarjeta, cuentas IBAN y correos.
Este filtro enmascara esos patrones en *cualquier* mensaje de log, incluso si un
desarrollador olvida no loguear el texto crudo.
"""

import logging
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # IBAN costarricense: CR + 20 dígitos (con o sin espacios)
    (re.compile(r"\bCR\d{2}(?:\s?\d){18}\b", re.IGNORECASE), "CR**IBAN**"),
    # Secuencias de 12+ dígitos (tarjetas, cuentas), permitiendo espacios o guiones
    (re.compile(r"\b(?:\d[ -]?){11,}\d\b"), "****"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
