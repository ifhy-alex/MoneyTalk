"""Conexión de Gmail desde la interfaz (OAuth con PKCE, permiso de solo lectura)."""

import logging
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from moneytalk.config import get_settings
from moneytalk.ingestion.banks import CR_BANKS
from moneytalk.ingestion.gmail import (
    GmailSource,
    finish_web_flow,
    start_web_flow,
    validate_client_secrets,
)
from moneytalk.pipeline import extra_senders

router = APIRouter(prefix="/gmail", tags=["gmail"])
log = logging.getLogger(__name__)

# state → (flow con su code_verifier, origen del frontend). Un solo usuario: memoria basta.
_PENDING: dict[str, tuple[Any, str]] = {}
_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class GmailStatus(BaseModel):
    has_credentials: bool
    connected: bool
    email: str | None
    mode: str
    banks: list[dict[str, Any]]
    extra_senders: list[str]
    error: str | None = None


@router.get("/status", response_model=GmailStatus)
def status() -> GmailStatus:
    s = get_settings()
    email = error = None
    connected = s.gmail_token_file.exists()
    if connected:
        try:
            email = GmailSource(s.gmail_token_file).profile_email()
        except Exception as exc:  # token revocado o vencido
            connected, error = False, f"El token de Gmail no es válido: {type(exc).__name__}"
    return GmailStatus(
        has_credentials=s.gmail_credentials_file.exists(),
        connected=connected,
        email=email,
        mode=f"etiqueta «{s.gmail_label}»"
        if s.gmail_label
        else "remitentes de bancos de Costa Rica",
        banks=[{"name": b.name, "domains": b.domains, "parser": b.parser} for b in CR_BANKS],
        extra_senders=extra_senders(s),
        error=error,
    )


@router.post("/credentials", status_code=204)
async def upload_credentials(file: Annotated[UploadFile, File()]) -> None:
    raw = await file.read()
    try:
        validate_client_secrets(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = get_settings().gmail_credentials_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


@router.get("/connect")
def connect(origin: Annotated[str, Query()]) -> dict[str, str]:
    """Inicia OAuth. `origin` es la URL del frontend (el callback pasa por su proxy /api)."""
    parsed = urlparse(origin)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=422, detail="Solo se permite conectar desde localhost")
    s = get_settings()
    if not s.gmail_credentials_file.exists():
        raise HTTPException(status_code=409, detail="Primero subí el JSON del cliente OAuth")
    base = f"{parsed.scheme}://{parsed.netloc}"
    url, state, flow = start_web_flow(s.gmail_credentials_file, f"{base}/api/gmail/callback")
    _PENDING.clear()  # solo una autorización en curso
    _PENDING[state] = (flow, base)
    return {"auth_url": url}


@router.get("/callback")
def callback(state: str, code: str | None = None, error: str | None = None) -> RedirectResponse:
    pending = _PENDING.pop(state, None)
    if pending is None:
        raise HTTPException(
            status_code=400, detail="Autorización desconocida o vencida; intentá de nuevo"
        )
    flow, base = pending
    if error or not code:
        return RedirectResponse(f"{base}/ingesta?gmail=cancelado")
    try:
        finish_web_flow(flow, code, get_settings().gmail_token_file)
    except Exception as exc:
        log.warning("OAuth de Gmail falló: %s", type(exc).__name__)
        return RedirectResponse(f"{base}/ingesta?gmail=error")
    return RedirectResponse(f"{base}/ingesta?gmail=conectado")


@router.post("/disconnect", status_code=204)
def disconnect() -> None:
    get_settings().gmail_token_file.unlink(missing_ok=True)
