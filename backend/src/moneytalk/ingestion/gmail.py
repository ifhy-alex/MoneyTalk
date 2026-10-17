"""Lector de Gmail con permiso de SOLO LECTURA, filtrado por etiqueta.

Configuración (una vez):
1. Google Cloud Console → crear proyecto → habilitar "Gmail API".
2. Pantalla de consentimiento OAuth en modo "Testing" con tu cuenta como usuario de prueba.
3. Credenciales → "OAuth client ID" tipo *Desktop app* → descargar como
   `data/gmail_credentials.json`.
4. En el host (no en Docker, porque abre el navegador): `uv run moneytalk gmail-auth`.
   Esto crea `data/gmail_token.json`, que el contenedor reutiliza.
5. En Gmail, creá un filtro que aplique la etiqueta (ej. `Finanzas/Bancos`) a los correos
   de notificaciones de tus bancos.
"""

import base64
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from moneytalk.ingestion.text import html_to_text
from moneytalk.ingestion.types import EmailMessage

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class MailSource(Protocol):
    def fetch(self, label: str, newer_than: date | None = None) -> Iterator[EmailMessage]: ...


def authorize(credentials_file: Path, token_file: Path) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")


def extract_body(payload: dict[str, Any]) -> str:
    """Prefiere text/plain; si solo hay HTML, lo convierte a texto."""
    plain: list[str] = []
    html: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    if html:
        # El HTML de los bancos conserva mejor la estructura Etiqueta/Valor.
        return html_to_text("\n".join(html))
    return "\n".join(plain)


def pdf_attachment_refs(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """(nombre, attachmentId) de cada adjunto PDF del mensaje."""
    refs: list[tuple[str, str]] = []

    def walk(part: dict[str, Any]) -> None:
        name = part.get("filename") or ""
        att_id = part.get("body", {}).get("attachmentId")
        is_pdf = part.get("mimeType") == "application/pdf" or name.lower().endswith(".pdf")
        if att_id and is_pdf:
            refs.append((name or "adjunto.pdf", att_id))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return refs


class GmailSource:
    def __init__(self, token_file: Path) -> None:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not token_file.exists():
            raise RuntimeError("Falta el token de Gmail: corré `uv run moneytalk gmail-auth`")
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _label_id(self, name: str) -> str:
        labels = self._service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label["name"] == name:
                return str(label["id"])
        raise RuntimeError(f"No existe la etiqueta de Gmail {name!r}")

    def _attachment(self, message_id: str, attachment_id: str) -> bytes:
        att = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return base64.urlsafe_b64decode(att["data"].encode("ascii"))

    def fetch(self, label: str, newer_than: date | None = None) -> Iterator[EmailMessage]:
        label_id = self._label_id(label)
        query = f"after:{newer_than:%Y/%m/%d}" if newer_than else None
        page_token: str | None = None
        while True:
            resp = (
                self._service.users()
                .messages()
                .list(userId="me", labelIds=[label_id], q=query, pageToken=page_token)
                .execute()
            )
            for ref in resp.get("messages", []):
                msg = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=ref["id"], format="full")
                    .execute()
                )
                headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
                attachments = tuple(
                    (name, self._attachment(msg["id"], att_id))
                    for name, att_id in pdf_attachment_refs(msg["payload"])
                )
                yield EmailMessage(
                    message_id=msg["id"],
                    sender=headers.get("from", ""),
                    subject=headers.get("subject", ""),
                    received_at=datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=UTC),
                    body_text=extract_body(msg["payload"]),
                    pdf_attachments=attachments,
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
