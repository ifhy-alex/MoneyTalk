from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.ingestion import service
from moneytalk.models import RawDocument, RawDocumentStatus, SourceType
from moneytalk.pipeline import ingest_gmail, on_new_transaction

router = APIRouter(prefix="/ingestion", tags=["ingesta"])
DB = Annotated[Session, Depends(get_db)]


class IngestResultOut(BaseModel):
    documents_new: int
    documents_skipped: int
    documents_failed: int
    transactions_created: int
    transactions_merged: int
    errors: list[str]


class RawDocumentOut(BaseModel):
    """Sin `content_text`: el texto crudo no sale por la API de listado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: SourceType
    subject: str | None
    received_at: datetime | None
    parser_name: str | None
    parser_version: str | None
    status: RawDocumentStatus
    error: str | None
    created_at: datetime


def _out(result: service.IngestResult) -> IngestResultOut:
    return IngestResultOut(**result.__dict__)


@router.post("/pdf", response_model=IngestResultOut)
async def upload_pdf(
    db: DB,
    file: Annotated[UploadFile, File()],
    password: Annotated[str | None, Form()] = None,
) -> IngestResultOut:
    data = await file.read()
    try:
        result = service.ingest_pdf(
            db, data, file.filename or "", password=password, on_new=on_new_transaction
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(result)


@router.post("/gmail", response_model=IngestResultOut)
def sync_gmail(db: DB, newer_than: date | None = None) -> IngestResultOut:
    try:
        result = ingest_gmail(db, get_settings(), newer_than)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _out(result)


@router.get("/documents", response_model=list[RawDocumentOut])
def list_documents(
    db: DB, status: RawDocumentStatus | None = None, limit: int = 100
) -> list[RawDocument]:
    stmt = select(RawDocument).order_by(RawDocument.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(RawDocument.status == status)
    return list(db.scalars(stmt))


@router.post("/documents/{doc_id}/reprocess", response_model=IngestResultOut)
def reprocess_document(db: DB, doc_id: int) -> IngestResultOut:
    raw = db.get(RawDocument, doc_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="documento no encontrado")
    return _out(service.reprocess(db, raw, on_new=on_new_transaction))


@router.post("/reprocess-outdated", response_model=IngestResultOut)
def reprocess_outdated(db: DB) -> IngestResultOut:
    total = service.IngestResult()
    for raw in service.outdated_documents(db):
        total.add(service.reprocess(db, raw, on_new=on_new_transaction))
    return _out(total)
