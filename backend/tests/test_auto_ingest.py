from collections.abc import Iterator
from pathlib import Path

import pymupdf
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.ingestion import service
from moneytalk.ingestion.gmail import pdf_attachment_refs
from moneytalk.ingestion.types import EmailMessage
from moneytalk.pipeline import ingest_gmail
from tests.helpers import statement_pdf


def _encrypted(data: bytes, password: str) -> bytes:
    doc = pymupdf.open(stream=data, filetype="pdf")
    out: bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        user_pw=password,
        owner_pw=password + "x",
    )
    doc.close()
    return out


def test_inbox_imports_and_moves_files(db: Session, tmp_path: Path) -> None:
    (tmp_path / "octubre.pdf").write_bytes(statement_pdf())
    (tmp_path / "protegido.pdf").write_bytes(_encrypted(statement_pdf("bac_tarjeta.txt"), "1234"))
    (tmp_path / "basura.pdf").write_bytes(b"no es un pdf")

    result = service.ingest_inbox(db, tmp_path, passwords=["0000", "1234"])
    # el protegido es el mismo estado: se descarta como duplicado después de abrirlo
    assert result.transactions_created == 4
    assert result.documents_failed == 1
    assert sorted(p.name.split("_", 1)[1] for p in (tmp_path / "procesados").iterdir()) == [
        "octubre.pdf",
        "protegido.pdf",
    ]
    assert [p.name.split("_", 1)[1] for p in (tmp_path / "errores").iterdir()] == ["basura.pdf"]
    assert not list(tmp_path.glob("*.pdf"))


def test_wrong_password_reports_error(db: Session, tmp_path: Path) -> None:
    (tmp_path / "x.pdf").write_bytes(_encrypted(statement_pdf(), "secreto"))
    result = service.ingest_inbox(db, tmp_path, passwords=["otra"])
    assert result.documents_failed == 1 and "contraseña" in result.errors[0]


def test_gmail_pdf_attachments_are_ingested(db: Session) -> None:
    msg = EmailMessage(
        "m1",
        "estados@banco.com",
        "Estado de cuenta",
        None,
        "Adjuntamos su estado de cuenta",
        pdf_attachments=(("estado.pdf", statement_pdf()),),
    )

    class Fake:
        def fetch(self, query: str) -> Iterator[EmailMessage]:
            yield msg

    result = ingest_gmail(db, Settings(), source=Fake())
    assert result.transactions_created == 4


def test_attachment_refs_found_in_nested_parts() -> None:
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": "eA"}},
            {
                "mimeType": "multipart/related",
                "parts": [
                    {
                        "mimeType": "application/octet-stream",
                        "filename": "EC.PDF",
                        "body": {"attachmentId": "a1"},
                    },
                    {
                        "mimeType": "image/png",
                        "filename": "logo.png",
                        "body": {"attachmentId": "a2"},
                    },
                ],
            },
        ],
    }
    assert pdf_attachment_refs(payload) == [("EC.PDF", "a1")]
