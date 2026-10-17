"""Utilidades de texto compartidas por los parsers."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "div", "br", "tr", "td", "th", "li", "table", "h1", "h2", "h3", "h4"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """HTML → texto con una línea por celda/párrafo, sin líneas vacías."""
    extractor = _TextExtractor()
    extractor.feed(html)
    lines = (
        re.sub(r"[ \t\xa0]+", " ", line).strip() for line in "".join(extractor.parts).split("\n")
    )
    return "\n".join(line for line in lines if line)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def parse_amount(raw: str) -> Decimal:
    """Convierte montos como '15,250.50', '15.250,50', '₡15 250,50' o '-100,000.00' a Decimal.

    El último separador (punto o coma) seguido de exactamente 2 dígitos se toma como decimal.
    """
    s = re.sub(r"[^\d,.\-]", "", raw.replace("−", "-"))
    negative = s.startswith("-") or raw.strip().endswith("-")
    s = s.replace("-", "")
    match = re.search(r"[.,](\d{2})$", s)
    if match:
        integer = re.sub(r"[.,]", "", s[: match.start()])
        s = f"{integer}.{match.group(1)}"
    else:
        s = re.sub(r"[.,]", "", s)
    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"monto inválido: {raw!r}") from exc
    return -value if negative else value


CURRENCY_ALIASES = {
    "CRC": "CRC",
    "COL": "CRC",
    "₡": "CRC",
    "¢": "CRC",
    "COLONES": "CRC",
    "USD": "USD",
    "US$": "USD",
    "$": "USD",
    "DOLARES": "USD",
    "DÓLARES": "USD",
}


def normalize_currency(raw: str) -> str:
    key = raw.strip().upper()
    if key not in CURRENCY_ALIASES:
        raise ValueError(f"moneda desconocida: {raw!r}")
    return CURRENCY_ALIASES[key]
