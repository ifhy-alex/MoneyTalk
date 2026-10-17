"""Quita los CheckConstraint duplicados que Alembic autogenera para Enums no nativos.

`sa.Enum(..., create_constraint=True)` ya crea su CHECK al crear la tabla; el autogenerate
además lo emite explícito (dos veces), lo que choca en Postgres. Uso:

    uv run python scripts/clean_enum_checks.py migrations/versions/<archivo>.py
"""

import sys
from pathlib import Path

_START = "sa.CheckConstraint("


def _matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    in_str: str | None = None
    for i in range(open_idx, len(text)):
        ch = text[i]
        if in_str:
            if ch == in_str and text[i - 1] != "\\":
                in_str = None
        elif ch in "\"'":
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("paréntesis sin cerrar")


def clean_source(source: str) -> tuple[str, int]:
    out: list[str] = []
    pos = removed = 0
    while (idx := source.find(_START, pos)) != -1:
        end = _matching_paren(source, idx + len(_START) - 1)
        body = source[idx:end]
        if " IN (" in body:
            line_start = source.rfind("\n", 0, idx)
            out.append(source[pos:line_start])
            pos = end + 1
            if source[pos : pos + 1] == ",":
                pos += 1
            removed += 1
        else:
            out.append(source[pos : end + 1])
            pos = end + 1
    out.append(source[pos:])
    return "".join(out), removed


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        path = Path(arg)
        cleaned, count = clean_source(path.read_text(encoding="utf-8"))
        path.write_text(cleaned, encoding="utf-8")
        print(f"{arg}: {count} constraints duplicados eliminados")
