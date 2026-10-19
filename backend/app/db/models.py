"""Database tables, declared with the SQLAlchemy 2.0 typed ORM."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Dialect,
    Enum,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Return a new random identifier, stored as text."""
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """Store datetimes in UTC and always read them back as timezone-aware.

    SQLite has no timezone support: without this type, a datetime saved as
    aware would come back naive, and the API would lose the "UTC" information.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use a UTC-aware datetime.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Parent class of every table."""


class DocumentStatus(StrEnum):
    """Lifecycle of an uploaded document."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    """An uploaded file and its processing status."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    page_count: Mapped[int] = mapped_column(default=0)
    ocr_used: Mapped[bool] = mapped_column(default=False)
    status: Mapped[DocumentStatus] = mapped_column(
        # Store the readable value ("ready") as plain text, not a database enum,
        # so adding a status later needs no schema change.
        Enum(
            DocumentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=DocumentStatus.UPLOADED,
    )
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Page.page_number",
    )


class Page(Base):
    """The extracted text of one page, kept so chunking can be redone without new OCR."""

    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    ocr_used: Mapped[bool] = mapped_column(default=False)

    document: Mapped[Document] = relationship(back_populates="pages")