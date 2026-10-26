"""Postgres embebido: los binarios viajan con la app (paquete `pgserver`) y los datos
quedan en la carpeta del usuario. Solo escucha en 127.0.0.1 y pide contraseña.
"""

import logging
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

USER = "moneytalk"
DB_NAME = "moneytalk"
# Sin ventana de consola para initdb/pg_ctl/postgres cuando corre la app con doble clic.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def pg_bin_dir() -> Path:
    """Carpeta `bin` de Postgres: dentro del ejecutable o en el paquete instalado."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "pginstall" / "bin"
    import pgserver

    return Path(pgserver.__file__).parent / "pginstall" / "bin"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


class EmbeddedPostgres:
    def __init__(self, root: Path, port: int | None = None) -> None:
        self.root = root
        self.data = root / "pgdata"
        self.pwfile = root / "pg.secret"
        self.logfile = root / "logs" / "postgres.log"
        self.port = port or free_port()
        self.bin = pg_bin_dir()

    def _exe(self, name: str) -> str:
        return str(self.bin / (name + (".exe" if os.name == "nt" else "")))

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603  binarios propios, argumentos sin shell
            list(args),
            capture_output=True,
            text=True,
            check=check,
            creationflags=_NO_WINDOW,
        )

    @property
    def password(self) -> str:
        return self.pwfile.read_text(encoding="utf-8").strip()

    @property
    def url(self) -> str:
        return f"postgresql+psycopg://{USER}:{self.password}@127.0.0.1:{self.port}/{DB_NAME}"

    def _init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.pwfile.exists():
            self.pwfile.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        log.info("Creando la base de datos local en %s", self.data)
        self._run(
            self._exe("initdb"),
            "-D", str(self.data),
            "-U", USER,
            "--pwfile", str(self.pwfile),
            "-A", "scram-sha-256",
            "-E", "UTF8",
            "--locale", "C",
        )  # fmt: skip

    def _status(self) -> bool:
        return (
            self._run(self._exe("pg_ctl"), "status", "-D", str(self.data), check=False).returncode
            == 0
        )

    def start(self) -> None:
        if not (self.data / "PG_VERSION").exists():
            self._init()
        if self._status():
            # Quedó encendido de una sesión que se cerró mal: apagarlo y arrancar limpio.
            log.warning("Había un Postgres huérfano de una sesión anterior; se reinicia")
            self.stop()
        else:
            (self.data / "postmaster.pid").unlink(missing_ok=True)
        self.logfile.parent.mkdir(parents=True, exist_ok=True)
        opts = f"-p {self.port} -c listen_addresses=127.0.0.1"
        # Sin tuberías: postgres hereda los handles de pg_ctl y run() esperaría para siempre.
        subprocess.run(  # noqa: S603
            [
                self._exe("pg_ctl"), "start", "-w", "-t", "60",
                "-D", str(self.data), "-l", str(self.logfile), "-o", opts,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            creationflags=_NO_WINDOW,
        )  # fmt: skip
        self._ensure_db()

    def _ensure_db(self) -> None:
        import psycopg

        dsn = (
            f"host=127.0.0.1 port={self.port} user={USER} password={self.password} dbname=postgres"
        )
        with psycopg.connect(dsn, autocommit=True) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)
            ).fetchone()
            if not exists:
                conn.execute(f'CREATE DATABASE "{DB_NAME}"')

    def stop(self) -> None:
        if self.data.exists():
            self._run(
                self._exe("pg_ctl"), "stop", "-D", str(self.data), "-m", "fast", "-w", check=False
            )
