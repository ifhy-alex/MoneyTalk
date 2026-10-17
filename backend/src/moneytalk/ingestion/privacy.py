"""Enmascarado de documentos antes de guardarlos.

El texto crudo se conserva para poder reprocesar, pero nunca con números completos de
cuenta/tarjeta/IBAN, teléfonos de SINPE ni el nombre del titular. Se dejan los últimos
4 dígitos, que es lo único que necesitan los parsers para identificar la cuenta.
"""

import re

# IBAN CR: CR + 2 de control + "0" + 3 del banco + 14 de cuenta. El código de banco no es
# sensible y permite reconocer la entidad, así que se conserva.
_IBAN = re.compile(r"\bCR\d{2}(?:\s?\d){18}\b", re.IGNORECASE)
_MASKED_IBAN = re.compile(r"\bCR\*\* 0(\d{3}) \*\*\*\* \d{4}\b")
_LONG_DIGITS = re.compile(r"(?<![\d*])(?:\d[ -]?){8,}(\d[ -]?){3}\d(?!\d)")
# Teléfonos de 8 dígitos (CR) dentro de textos de SINPE: "De 88887777 a 86665555"
_PHONE = re.compile(r"(?<!\d)[2-8]\d{7}(?!\d)")
_HOLDER = re.compile(r"(?im)^(\s*(?:Titular|Cliente|Nombre)\s*:\s*)(.+?)(\s{2,}|$)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _mask_iban(match: re.Match[str]) -> str:
    digits = _digits(match.group(0))
    return f"CR** 0{digits[3:6]} **** {digits[-4:]}"


def _keep_last4(match: re.Match[str]) -> str:
    return f"****{_digits(match.group(0))[-4:]}"


def iban_bank_code(text: str) -> str | None:
    """Código de banco de un IBAN ya enmascarado (p. ej. '161')."""
    m = _MASKED_IBAN.search(text)
    return m.group(1) if m else None


def redact_document(text: str) -> str:
    text = _IBAN.sub(_mask_iban, text)
    text = _LONG_DIGITS.sub(_keep_last4, text)
    text = _PHONE.sub("********", text)
    text = _HOLDER.sub(lambda m: f"{m.group(1)}<titular>{m.group(3)}", text)
    return _EMAIL.sub("<email>", text)
