import hashlib
from typing import Any

import pymupdf


def pdf_to_text(data: bytes, password: str | None = None) -> str:
    """Texto del PDF en orden de lectura (sort=True ordena por posición, no por stream).

    Muchos bancos protegen el estado de cuenta (p. ej. con la cédula). La contraseña se usa
    solo en memoria para abrirlo y nunca se guarda.
    """
    try:
        doc: Any = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("el archivo no es un PDF válido") from exc
    with doc:
        if doc.needs_pass and not (password and doc.authenticate(password)):
            raise ValueError("PDF protegido: indicá la contraseña para abrirlo")
        return "\n".join(page.get_text("text", sort=True) for page in doc)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
