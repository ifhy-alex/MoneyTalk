from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from moneytalk.ingestion.text import html_to_text
from moneytalk.ingestion.types import EmailMessage

FIXTURES = Path(__file__).parent / "fixtures"


def email_fixture(name: str, sender: str, message_id: str | None = None) -> EmailMessage:
    raw = (FIXTURES / "emails" / name).read_text(encoding="utf-8")
    body = html_to_text(raw) if name.endswith(".html") else raw
    return EmailMessage(
        message_id=message_id or name,
        sender=sender,
        subject="Notificación de transacción",
        received_at=datetime(2026, 10, 16, 20, 40, tzinfo=UTC),
        body_text=body,
    )


def text_to_pdf(text: str) -> bytes:
    """Genera un PDF sintético (sin datos reales) con una línea de texto por renglón."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 50.0
    for line in text.splitlines():
        page.insert_text((40, y), line, fontname="cour", fontsize=8)
        y += 12
    data: bytes = doc.tobytes()
    doc.close()
    return data


def statement_pdf(name: str = "bac_tarjeta.txt") -> bytes:
    return text_to_pdf((FIXTURES / "statements" / name).read_text(encoding="utf-8"))
