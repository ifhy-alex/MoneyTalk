"""Registro de parsers. Para agregar un banco: implementá la interfaz y agregalo aquí."""

from moneytalk.ingestion.parsers.bac import BacEmailParser, BacStatementParser
from moneytalk.ingestion.parsers.base import EmailParser, ParseError, StatementParser
from moneytalk.ingestion.parsers.bn import BnEmailParser
from moneytalk.ingestion.types import EmailMessage

EMAIL_PARSERS: list[EmailParser] = [BacEmailParser(), BnEmailParser()]
STATEMENT_PARSERS: list[StatementParser] = [BacStatementParser()]


def find_email_parser(message: EmailMessage) -> EmailParser | None:
    return next((p for p in EMAIL_PARSERS if p.can_parse(message)), None)


def find_statement_parser(text: str) -> StatementParser | None:
    return next((p for p in STATEMENT_PARSERS if p.can_parse(text)), None)


def parser_by_name(name: str) -> EmailParser | StatementParser | None:
    all_parsers: list[EmailParser | StatementParser] = [*EMAIL_PARSERS, *STATEMENT_PARSERS]
    return next((p for p in all_parsers if p.name == name), None)


__all__ = [
    "EMAIL_PARSERS",
    "STATEMENT_PARSERS",
    "EmailParser",
    "ParseError",
    "StatementParser",
    "find_email_parser",
    "find_statement_parser",
    "parser_by_name",
]
