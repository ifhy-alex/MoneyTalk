"""Punto de entrada del ejecutable: `python -m moneytalk.desktop` o `MoneyTalk.exe`.

Al abrir: Postgres embebido → migraciones → API (que también sirve el frontend) →
tareas programadas → ventana. Al cerrar la ventana se apaga todo en orden inverso.
"""

import atexit
import contextlib
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import IO, Any

log = logging.getLogger("moneytalk.desktop")

APP_NAME = "MoneyTalk"
# Puerto fijo: el origen (y con él lo que el frontend guarda en localStorage) no cambia
# entre sesiones. Si está ocupado se usa uno libre.
PREFERRED_PORT = 8765

ENV_TEMPLATE = """\
# Configuración opcional de MoneyTalk. Quitá el # y completá lo que quieras usar;
# después cerrá y volvé a abrir la app. Sin nada de esto la app funciona igual.

# Claude: categoriza movimientos dudosos y resume reportes trimestrales.
# ANTHROPIC_API_KEY=

# Tipo de cambio oficial del BCCR (registro gratuito en gee.bccr.fi.cr).
# BCCR_EMAIL=
# BCCR_TOKEN=

# Alertas por Telegram.
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=

# Contraseñas de estados de cuenta en PDF protegidos, separadas por coma.
# STATEMENT_PDF_PASSWORDS=
"""


def app_home() -> Path:
    override = os.environ.get("MONEYTALK_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def resource_dir() -> Path:
    """Donde viajan migraciones y frontend: el bundle de PyInstaller o el repositorio."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle)
    return Path(__file__).resolve().parents[3]  # backend/


def _paths() -> tuple[Path, Path]:
    res = resource_dir()
    if getattr(sys, "_MEIPASS", None):
        return res / "migrations", res / "web"
    return res / "migrations", res.parent / "frontend" / "dist"


def _message(text: str, error: bool = False) -> None:
    if os.name == "nt":
        import ctypes

        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, flags)
    else:
        print(text, file=sys.stderr)


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


class SingleInstance:
    """Candado de archivo: evita dos copias peleando por la misma base de datos."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: IO[str] | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = self.path.open("a+", encoding="utf-8")
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True


def _setup_logging(home: Path) -> None:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    # Con doble clic no hay consola: stdout/stderr son None y cualquier print fallaría.
    if sys.stdout is None or sys.stderr is None:
        stream = (logs / "moneytalk.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream


class Services:
    """Postgres, API y scheduler, con un apagado idempotente."""

    def __init__(self, home: Path) -> None:
        from moneytalk.desktop.postgres import EmbeddedPostgres

        self.home = home
        self.pg = EmbeddedPostgres(home)
        self.port = PREFERRED_PORT if _port_free(PREFERRED_PORT) else 0
        self.server: Any = None
        self.scheduler: Any = None
        self._thread: threading.Thread | None = None
        self._stopped = False
        self._stop_lock = threading.Lock()
        # Si la ventana se cierra durante el arranque, stop() espera a que el arranque llegue
        # a un punto seguro (que lo abandona al ver `closing`) y recién entonces apaga.
        self._start_lock = threading.Lock()
        self.closing = threading.Event()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _configure_env(self) -> None:
        data = self.home / "data"
        (data / "inbox").mkdir(parents=True, exist_ok=True)
        env_file = self.home / ".env"
        if not env_file.exists():
            env_file.write_text(ENV_TEMPLATE, encoding="utf-8")
        _, web = _paths()
        os.chdir(self.home)  # Settings lee `.env` del directorio actual
        os.environ.update(
            {
                "DESKTOP_MODE": "1",
                "DATABASE_URL": self.pg.url,
                "DATA_DIR": str(data),
                "GMAIL_CREDENTIALS_FILE": str(data / "gmail_credentials.json"),
                "GMAIL_TOKEN_FILE": str(data / "gmail_token.json"),
                "INBOX_DIR": str(data / "inbox"),
                "STATIC_DIR": str(web),
                "CORS_ORIGINS": f'["{self.url}"]',
            }
        )

    def _migrate(self) -> None:
        from alembic import command
        from alembic.config import Config

        migrations, _ = _paths()
        cfg = Config()
        cfg.set_main_option("script_location", str(migrations))
        command.upgrade(cfg, "head")

    def start(self) -> None:
        with self._start_lock:
            if not self.closing.is_set():
                self._start()

    def _start(self) -> None:
        atexit.register(self.stop)
        self.pg.start()
        if self.port == 0:
            from moneytalk.desktop.postgres import free_port

            self.port = free_port()
        self._configure_env()

        from moneytalk.config import get_settings
        from moneytalk.log import configure_logging

        get_settings.cache_clear()
        configure_logging(get_settings().log_level)
        log.info("Datos en %s", self.home)
        with contextlib.suppress(Exception):
            import yfinance

            yfinance.set_tz_cache_location(str(self.home / "cache"))
        self._migrate()
        if self.closing.is_set():
            return

        import uvicorn

        from moneytalk.main import create_app

        config = uvicorn.Config(
            create_app(),
            host="127.0.0.1",
            port=self.port,
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=3,  # no esperar indefinidamente al navegador
        )
        self.server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self.server.run, name="api", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 30
        while not self.server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("La API no logró arrancar")
            time.sleep(0.05)

        from apscheduler.schedulers.background import BackgroundScheduler

        from moneytalk.scheduler import build_scheduler

        self.scheduler = build_scheduler(BackgroundScheduler)
        self.scheduler.start()
        log.info("MoneyTalk listo en %s", self.url)

    def stop(self) -> None:
        self.closing.set()
        # Con candados: si se llama dos veces (cierre de ventana y atexit), la segunda espera
        # a que termine la primera; y nunca se apaga a la mitad de un arranque.
        with self._start_lock, self._stop_lock:
            if self._stopped:
                return
            log.info("Apagando MoneyTalk")
            if self.scheduler is not None:
                with contextlib.suppress(Exception):
                    self.scheduler.shutdown(wait=False)
            if self.server is not None:
                self.server.should_exit = True
                if self._thread is not None:
                    self._thread.join(timeout=4)
                    if self._thread.is_alive():
                        # Una conexión keep-alive del navegador puede frenar el cierre ordenado.
                        self.server.force_exit = True
                        self._thread.join(timeout=3)
                log.info("API detenida")
            with contextlib.suppress(Exception):
                from moneytalk.db import get_engine

                get_engine().dispose()
            self.pg.stop()
            log.info("Base de datos detenida")
            self._stopped = True


LOADING_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{color-scheme:light dark}
body{margin:0;height:100vh;display:grid;place-items:center;
font:15px "Segoe UI",system-ui,sans-serif;background:#0c1310;color:#e8ece3}
@media (prefers-color-scheme:light){body{background:#eceee8;color:#14201b}}
.b{width:160px;height:3px;background:#52c99a33;overflow:hidden;border-radius:2px;margin:18px auto 0}
.b i{display:block;width:40%;height:100%;background:#52c99a;animation:m 1.1s ease-in-out infinite}
@keyframes m{from{transform:translateX(-100%)}to{transform:translateX(250%)}}
@media (prefers-reduced-motion:reduce){.b i{animation:none;width:100%}}
h1{font:600 30px Georgia,"Times New Roman",serif;letter-spacing:-.02em;margin:0}
p{opacity:.7;margin:6px 0 0}</style></head>
<body><div style="text-align:center"><h1>MoneyTalk</h1>
<p>Preparando tus datos…</p><div class="b"><i></i></div></div></body></html>"""


def _run_window(services: Services) -> None:
    """Ventana nativa (WebView2). Si no está disponible, navegador + ventanita para cerrar."""
    try:
        import webview
    except Exception:
        log.exception("pywebview no disponible; se usa el navegador")
        _run_browser_fallback(services)
        return

    window = webview.create_window(
        APP_NAME, html=LOADING_HTML, width=1280, height=840, min_size=(380, 600)
    )
    if window is None:
        raise RuntimeError("No se pudo crear la ventana")
    # Empezar a apagar apenas se cierra la ventana; main() espera a que termine.
    window.events.closed += services.stop
    failure: list[BaseException] = []

    def boot() -> None:
        try:
            services.start()
            if not services.closing.is_set():
                window.load_url(services.url)
        except BaseException as exc:
            if services.closing.is_set():
                return  # se cerró durante el arranque: no es un error
            failure.append(exc)
            log.exception("No se pudo iniciar MoneyTalk")
            window.destroy()

    webview.start(
        boot,
        private_mode=False,  # conservar preferencias del frontend entre sesiones
        storage_path=str(services.home / "webview"),
    )
    if failure:
        raise failure[0]


def _run_browser_fallback(services: Services) -> None:
    import tkinter as tk
    import webbrowser

    services.start()
    webbrowser.open(services.url)
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("340x130")
    tk.Label(root, text="MoneyTalk está abierta en tu navegador.", pady=12).pack()
    tk.Button(root, text="Abrir de nuevo", command=lambda: webbrowser.open(services.url)).pack()
    tk.Button(root, text="Cerrar MoneyTalk", command=root.destroy).pack(pady=6)
    root.mainloop()


def main() -> int:
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    _setup_logging(home)
    lock = SingleInstance(home / "app.lock")
    if not lock.acquire():
        _message("MoneyTalk ya está abierta.")
        return 0
    services = Services(home)
    try:
        _run_window(services)
    except Exception as exc:
        _message(
            f"MoneyTalk no pudo iniciar: {exc}\n\nDetalles en {home / 'logs'}",
            error=True,
        )
        return 1
    finally:
        services.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
