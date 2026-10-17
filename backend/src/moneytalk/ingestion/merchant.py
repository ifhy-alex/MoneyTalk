"""Normalización de nombres de comercio.

El mismo comercio llega distinto por correo ("AUTO MERCADO ESCAZU SAN JOSE CR") y en el
estado de cuenta ("AUTOMERCADO ESCAZU"). Normalizar ayuda a deduplicar y a que una sola
regla de categoría cubra todas las variantes.
"""

import re
from difflib import SequenceMatcher

from moneytalk.ingestion.text import strip_accents

_PAYMENT_PREFIXES = re.compile(r"^(PAYPAL|SQ|SP|TST|DLO|DLOCAL|MP|PY)\s*\*\s*")
_COUNTRY_SUFFIX = re.compile(
    r"\b(SAN JOSE|HEREDIA|ALAJUELA|CARTAGO|CR|CRI|COSTA RICA|US|USA)\b\s*$"
)
_NOISE = re.compile(r"[^A-Z0-9& ]+")
_DIGITS = re.compile(r"\b\d{3,}\b")


def normalize_merchant(raw: str) -> str:
    s = strip_accents(raw).upper().strip()
    s = _PAYMENT_PREFIXES.sub("", s)
    s = re.sub(r"^G\s?GLE\b", "GOOGLE", s)  # "G gle" = Google en algunos bancos
    s = s.replace(".COM", "").replace("*", " ")
    s = _NOISE.sub(" ", s)
    s = _DIGITS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Quitar sufijos de ciudad/país repetidamente ("ESCAZU SAN JOSE CR")
    previous = None
    while previous != s:
        previous = s
        s = _COUNTRY_SUFFIX.sub("", s).strip()
    return s or strip_accents(raw).upper().strip()


def merchant_similarity(a: str, b: str) -> float:
    a_n, b_n = normalize_merchant(a), normalize_merchant(b)
    if not a_n or not b_n:
        return 0.0
    if a_n in b_n or b_n in a_n:
        return 1.0
    return SequenceMatcher(None, a_n.replace(" ", ""), b_n.replace(" ", "")).ratio()
