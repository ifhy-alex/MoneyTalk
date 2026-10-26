# PyInstaller: empaqueta MoneyTalk como app de escritorio (carpeta con MoneyTalk.exe).
# Se corre desde desktop/build.ps1, que primero compila el frontend.
# ruff: noqa
from pathlib import Path

import pgserver
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"
PG = Path(pgserver.__file__).parent / "pginstall"

# Postgres embebido: solo lo que necesita para correr (sin headers ni librerías estáticas).
pg_datas = [(str(PG / "bin"), "pginstall/bin"), (str(PG / "share"), "pginstall/share")]
pg_datas += [
    (str(f), str(Path("pginstall") / f.parent.relative_to(PG)))
    for f in (PG / "lib").rglob("*")
    if f.is_file() and f.suffix.lower() == ".dll"
]

datas = [
    (str(BACKEND / "migrations"), "migrations"),
    (str(ROOT / "frontend" / "dist"), "web"),
    *pg_datas,
    *collect_data_files("yfinance"),
    *collect_data_files("certifi"),
]

hiddenimports = [
    *collect_submodules("moneytalk"),
    *collect_submodules("uvicorn"),
    *collect_submodules("apscheduler"),
    "alembic.ext",
    "psycopg_binary",
]

a = Analysis(
    [str(BACKEND / "src" / "moneytalk" / "desktop" / "__main__.py")],
    pathex=[str(BACKEND / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "mypy", "ruff", "IPython", "matplotlib", "PyQt5", "PyQt6", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MoneyTalk",
    icon=str(ROOT / "desktop" / "moneytalk.ico"),
    console=False,  # sin ventana negra de consola
    upx=False,  # UPX dispara falsos positivos de antivirus
)

coll = COLLECT(exe, a.binaries, a.datas, name="MoneyTalk", upx=False)
