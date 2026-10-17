"""Lector de Gmail con permiso de SOLO LECTURA.

Por defecto busca los correos de los bancos de Costa Rica por remitente (ver `banks.py`);
opcionalmente se puede limitar a una etiqueta de Gmail.

Configuración (una vez), desde la página Ingesta de la app:
1. Google Cloud Console → crear proyecto → habilitar "Gmail API".
2. Pantalla de consentimiento OAuth en modo "Testing", con tu cuenta como usuario de prueba.
3. Credenciales → "OAuth client ID" tipo *Desktop app* → descargar el JSON.
4. Subir ese JSON en Ingesta → "Conectar Gmail" → autorizar en la ventana de Google.
   (Alternativa por consola, en el host: `uv run moneytalk gmail-auth`.)
"""

import base64
import json
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from moneytalk.ingestion.banks import sender_query
from moneytalk.ingestion.text import html_to_text
from moneytalk.ingestion.types import EmailMessage

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class MailSource(Protocol):
    def fetch(self, query: str) -> Iterator[EmailMessage]: ...


def build_query(label: str, extra_senders: list[str], newer_than: date | None) -> str:
    """Etiqueta si está configurada; si no, remitentes de bancos de CR."""
    if label:
        base = "label:" + label.strip().lower().replace("/", "-").replace(" ", "-")
    else:
        base = sender_query(extra_senders)
    return f"{base} after:{newer_than:%Y/%m/%d}" if newer_than else base


def validate_client_secrets(raw: bytes) -> dict[str, Any]:
    """Comprueba que el JSON sea un cliente OAuth de Google (tipo Desktop o Web)."""
    try:
        data: dict[str, Any] = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El archivo no es un JSON válido") from exc
    kind = next((k for k in ("installed", "web") if k in data), None)
    if kind is None or "client_id" not in data[kind] or "client_secret" not in data[kind]:
        raise ValueError("No parece un 'OAuth client ID' de Google (falta installed/web)")
    return data


def start_web_flow(credentials_file: Path, redirect_uri: str) -> tuple[str, str, Any]:
    """Devuelve (URL de autorización, state, flow con su PKCE para completar el callback)."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(str(credentials_file), SCOPES, redirect_uri=redirect_uri)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    return url, str(state), flow


def finish_web_flow(flow: Any, code: str, token_file: Path) -> None:
    flow.fetch_token(code=code)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(flow.credentials.to_json(), encoding="utf-8")


def authorize(credentials_file: Path, token_file: Path) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")


def extract_body(payload: dict[str, Any]) -> str:
    """Prefiere el HTML convertido a texto (conserva Etiqueta/Valor); si no, text/plain."""
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
            raise RuntimeError("Gmail no está conectado: conectalo desde la página Ingesta")
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def profile_email(self) -> str:
        profile = self._service.users().getProfile(userId="me").execute()
        return str(profile.get("emailAddress", ""))

    def _attachment(self, message_id: str, attachment_id: str) -> bytes:
        att = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return base64.urlsafe_b64decode(att["data"].encode("ascii"))

    def fetch(self, query: str) -> Iterator[EmailMessage]:
        page_token: str | None = None
        while True:
            resp = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=100)
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
