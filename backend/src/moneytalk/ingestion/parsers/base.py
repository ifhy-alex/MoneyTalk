"""Interfaz común de parsers (patrón estrategia).

Agregar un banco nuevo = crear una clase que herede de `EmailParser` o `StatementParser`
y registrarla en `moneytalk.ingestion.parsers.__init__`. Nada más cambia.

Cada parser declara `name` y `version`; la versión se guarda en `raw_documents` y permite
reprocesar solo los documentos leídos con una versión vieja.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from moneytalk.ingestion.types import EmailMessage, ParsedTransaction


class ParseError(Exception):
    """El documento parecía de este banco pero no se pudo extraer la información."""


class EmailParser(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    institution: ClassVar[str]

    @abstractmethod
    def can_parse(self, message: EmailMessage) -> bool:
        """Debe ser barato y conservador: remitente y/o asunto."""

    @abstractmethod
    def parse(self, message: EmailMessage) -> list[ParsedTransaction]:
        """Lista vacía = el correo es del banco pero no es una transacción (ej. promoción)."""


class StatementParser(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    institution: ClassVar[str]

    @abstractmethod
    def can_parse(self, text: str) -> bool: ...

    @abstractmethod
    def parse(self, text: str) -> list[ParsedTransaction]: ...
