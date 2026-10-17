import enum
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from moneytalk.models.base import Base, str_enum


class SourceType(enum.StrEnum):
    EMAIL = "email"
    PDF_STATEMENT = "pdf_statement"


class RawDocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    IGNORED = "ignored"


class RawDocument(Base):
    """Todo lo que entra al sistema, tal cual, para poder reprocesarlo si un parser mejora."""

    __tablename__ = "raw_documents"
    __table_args__ = (UniqueConstraint("source_type", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, "source_type"))
    external_id: Mapped[str] = mapped_column(String(128))
    sender: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    parser_name: Mapped[str | None] = mapped_column(String(64))
    parser_version: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[RawDocumentStatus] = mapped_column(
        str_enum(RawDocumentStatus, "raw_document_status"), default=RawDocumentStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
