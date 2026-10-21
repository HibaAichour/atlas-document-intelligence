"""Database tables, declared with the SQLAlchemy 2.0 typed ORM."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
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


def text_enum(enum_class: type[StrEnum]) -> Enum:
    """Store an enum as its readable value ("ready", "user"), as plain text.

    Not a database enum, so adding a value later needs no schema change.
    """
    return Enum(
        enum_class,
        native_enum=False,
        length=20,
        values_callable=lambda members: [member.value for member in members],
    )


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
        text_enum(DocumentStatus), default=DocumentStatus.UPLOADED
    )
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Page.page_number",
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by=lambda: [Chunk.page_number, Chunk.position],
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


class Chunk(Base):
    """A searchable piece of one page.

    SQLite is the source of truth for the text. The vector store only keeps
    the embedding and metadata under the same id, so the index can always be
    rebuilt from this table.
    """

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "page_number", "position"),)

    # Text uuid, generated before saving: the same id is used in the vector store.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]  # same numbering as Page, shown in citations
    position: Mapped[int]  # 0-based order of the chunk within its page
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    document: Mapped[Document] = relationship(back_populates="chunks")


class MessageRole(StrEnum):
    """Who wrote a message."""

    USER = "user"
    ASSISTANT = "assistant"


class MessageMode(StrEnum):
    """The kind of request a message belongs to ("extract" arrives at step 9)."""

    ASK = "ask"
    EXTRACT = "extract"


class ChatSession(Base):
    """A conversation: its messages and the documents it uses.

    Named ChatSession, not Session, so it is never confused with the
    SQLAlchemy Session that talks to the database.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # None until the first question, which then gives the session its title.
    title: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.position",
    )
    document_links: Mapped[list["SessionDocument"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """One question or one answer in a session.

    Answers keep a full copy of their sources (text, file name, page):
    re-indexing creates new chunk ids, and a copy keeps old citations clickable.
    """

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]  # 0-based order within the session
    role: Mapped[MessageRole] = mapped_column(text_enum(MessageRole))
    mode: Mapped[MessageMode] = mapped_column(text_enum(MessageMode), default=MessageMode.ASK)
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Agents that ran for this answer (name, duration, status), filled from step 9.
    agent_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Answer details, so a restored answer looks exactly like a live one.
    # Always None (or empty) for user messages.
    status: Mapped[str | None] = mapped_column(String(20), default=None)
    refusal_reason: Mapped[str | None] = mapped_column(String(50), default=None)
    invalid_citations: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    best_score: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class SessionDocument(Base):
    """A document selected in a session.

    Deleting either the session or the document removes the link.
    """

    __tablename__ = "session_documents"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    session: Mapped[ChatSession] = relationship(back_populates="document_links")