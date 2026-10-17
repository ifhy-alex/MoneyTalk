"""CLI: `uv run moneytalk <comando>` (o `docker compose exec api moneytalk <comando>`)."""

import argparse
import getpass
import json
from collections.abc import Callable
from pathlib import Path

from moneytalk.config import get_settings
from moneytalk.db import get_sessionmaker
from moneytalk.ingestion import service
from moneytalk.log import configure_logging
from moneytalk.pipeline import ingest_gmail, on_new_transaction

Command = Callable[[argparse.Namespace], None]
COMMANDS: dict[str, tuple[str, Command, Callable[[argparse.ArgumentParser], None] | None]] = {}


def command(
    name: str, help_text: str, args: Callable[[argparse.ArgumentParser], None] | None = None
) -> Callable[[Command], Command]:
    def deco(fn: Command) -> Command:
        COMMANDS[name] = (help_text, fn, args)
        return fn

    return deco


def _print(result: object) -> None:
    print(
        json.dumps(getattr(result, "__dict__", result), indent=2, default=str, ensure_ascii=False)
    )


@command("gmail-auth", "Autoriza Gmail (solo lectura) y guarda el token en data/")
def _gmail_auth(_: argparse.Namespace) -> None:
    from moneytalk.ingestion.gmail import authorize

    s = get_settings()
    authorize(s.gmail_credentials_file, s.gmail_token_file)
    print(f"Token guardado en {s.gmail_token_file}")


@command("ingest-gmail", "Lee correos nuevos de la etiqueta configurada")
def _ingest_gmail(_: argparse.Namespace) -> None:
    with get_sessionmaker()() as db:
        _print(ingest_gmail(db, get_settings()))


def _pdf_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--password", action="store_true", help="pedir contraseña del PDF")


@command("ingest-pdf", "Importa uno o varios estados de cuenta en PDF", _pdf_args)
def _ingest_pdf(ns: argparse.Namespace) -> None:
    password = getpass.getpass("Contraseña del PDF: ") if ns.password else None
    total = service.IngestResult()
    with get_sessionmaker()() as db:
        for path in ns.paths:
            total.add(
                service.ingest_pdf(
                    db, path.read_bytes(), path.name, password=password, on_new=on_new_transaction
                )
            )
    _print(total)


@command("reprocess", "Reprocesa documentos fallidos o leídos con parsers viejos")
def _reprocess(_: argparse.Namespace) -> None:
    total = service.IngestResult()
    with get_sessionmaker()() as db:
        for raw in service.outdated_documents(db):
            total.add(service.reprocess(db, raw, on_new=on_new_transaction))
    _print(total)


def main(argv: list[str] | None = None) -> None:
    configure_logging(get_settings().log_level)
    parser = argparse.ArgumentParser(prog="moneytalk")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, (help_text, _, add_args) in COMMANDS.items():
        sp = sub.add_parser(name, help=help_text)
        if add_args:
            add_args(sp)
    ns = parser.parse_args(argv)
    COMMANDS[ns.cmd][1](ns)


if __name__ == "__main__":
    main()
