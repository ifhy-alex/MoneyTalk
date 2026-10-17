"""Helpers compartidos por los parsers de bancos costarricenses."""

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from moneytalk.ingestion.text import strip_accents

CR_TZ = ZoneInfo("America/Costa_Rica")

_MONTHS = {
    "JAN": 1, "ENE": 1, "FEB": 2, "MAR": 3, "APR": 4, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DEC": 12, "DIC": 12,
}  # fmt: skip


def label_fields(text: str, labels: list[str]) -> dict[str, str]:
    """Extrae valores 'Etiqueta: valor' donde el valor puede estar en la misma línea o la
    siguiente (así queda una tabla HTML de dos columnas al convertirla a texto)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    wanted = {strip_accents(label).lower(): label for label in labels}
    found: dict[str, str] = {}
    for i, line in enumerate(lines):
        key, sep, value = line.partition(":")
        norm = strip_accents(key).strip().lower()
        if sep and norm in wanted and wanted[norm] not in found:
            value = value.strip()
            if not value and i + 1 < len(lines):
                value = lines[i + 1]
            found[wanted[norm]] = value
    return found


def parse_cr_datetime(raw: str) -> tuple[date, datetime | None]:
    """Acepta 'Oct 16, 2026, 14:35', '16/10/2026 14:35', '16-10-2026' y '16 OCT 2026'."""
    s = strip_accents(raw).upper().strip()
    hm = re.search(r"(\d{1,2}):(\d{2})", s)
    t = time(int(hm.group(1)), int(hm.group(2))) if hm else None

    if m := re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s):
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    elif m := re.search(r"([A-Z]{3})[A-Z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s):
        d = date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
    elif m := re.search(r"(\d{1,2})\s+([A-Z]{3})[A-Z]*\.?\s+(\d{4})", s):
        d = date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
    else:
        raise ValueError(f"fecha no reconocida: {raw!r}")
    return d, datetime.combine(d, t, tzinfo=CR_TZ) if t else None
