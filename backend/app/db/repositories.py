"""Read and write the database. Routes and services never write SQL directly."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    ChatSession,
    Chunk,
    Document,
    DocumentStatus,
    Message,
    MessageMode,
    MessageRole,
    Page,
    SessionDocument,
    new_uuid,
    utc_now,
)
from app.ingestion.chunking import TextChunk
from app.ingestion.models import PageText

MAX_ERROR_LENGTH = 1000
MAX_TITLE_LENGTH = 60


class DocumentRepository:
    """Every database operation on documents, their pages and their chunks."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, filename: str, mime_type: str) -> Document:
        """Register a newly uploaded document with the status "uploaded"."""
        document = Document(filename=filename, mime_type=mime_type)
        self._session.add(document)
        self._session.commit()
        return document

    def get(self, document_id: str) -> Document | None:
        """Return the document, or None if the id is unknown."""
        return self._session.get(Document, document_id)

    def list_all(self) -> list[Document]:
        """Return every document, newest first."""
        statement = select(Document).order_by(Document.created_at.desc())
        return list(self._session.scalars(statement))

    def list_pages(self, document_id: str) -> list[Page]:
        """Return the pages of a document, in page order."""
        statement = (
            select(Page).where(Page.document_id == document_id).order_by(Page.page_number)
        )
        return list(self._session.scalars(statement))

    def mark_processing(self, document: Document) -> None:
        """Record that text extraction has started."""
        document.status = DocumentStatus.PROCESSING
        document.error = None
        self._session.commit()

    def mark_ready(self, document: Document, pages: Sequence[PageText]) -> None:
        """Store the extracted pages and mark the document as ready."""
        self._replace_pages(document, pages)
        document.page_count = len(pages)
        document.ocr_used = any(page.ocr_used for page in pages)
        document.status = DocumentStatus.READY
        document.error = None
        self._session.commit()

    def mark_failed(self, document: Document, error: str) -> None:
        """Record why processing failed. Any partial pages and chunks are removed."""
        document.chunks.clear()
        self._replace_pages(document, [])
        document.page_count = 0
        document.ocr_used = False
        document.status = DocumentStatus.FAILED
        document.error = error[:MAX_ERROR_LENGTH]
        self._session.commit()

    def replace_chunks(self, document: Document, chunks: Sequence[TextChunk]) -> list[Chunk]:
        """Delete the document's chunks, store the new ones and return them.

        Ids are generated here, before saving, so the caller can reuse them
        in the vector store.
        """
        # Delete first: a (page_number, position) pair that still exists
        # would break the uniqueness rule.
        document.chunks.clear()
        self._session.flush()
        stored = [
            Chunk(
                id=new_uuid(),
                page_number=chunk.page_number,
                position=chunk.position,
                text=chunk.text,
            )
            for chunk in chunks
        ]
        document.chunks.extend(stored)
        self._session.commit()
        return stored

    def list_chunks(self, document_id: str) -> list[Chunk]:
        """Return the chunks of a document, in page order then position order."""
        statement = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.page_number, Chunk.position)
        )
        return list(self._session.scalars(statement))

    def get_chunks(self, chunk_ids: Sequence[str]) -> list[Chunk]:
        """Return the chunks with these ids, in the same order as chunk_ids.

        Unknown ids are skipped. Each chunk comes with its document loaded,
        so the caller can read the filename without another query.
        """
        if not chunk_ids:
            return []
        statement = (
            select(Chunk).where(Chunk.id.in_(chunk_ids)).options(joinedload(Chunk.document))
        )
        found = {chunk.id: chunk for chunk in self._session.scalars(statement)}
        return [found[chunk_id] for chunk_id in chunk_ids if chunk_id in found]

    def _replace_pages(self, document: Document, pages: Sequence[PageText]) -> None:
        # Delete the old pages first: inserting a page number that still
        # exists would break the (document_id, page_number) uniqueness rule.
        document.pages.clear()
        self._session.flush()
        document.pages.extend(
            Page(page_number=page.page_number, text=page.text, ocr_used=page.ocr_used)
            for page in pages
        )


def make_session_title(question: str) -> str:
    """Turn the first question of a session into a short, one-line title.

    Spaces and line breaks are collapsed. A long question is cut at the last
    whole word that fits, and "…" shows that it was cut.
    """
    title = " ".join(question.split())
    if len(title) <= MAX_TITLE_LENGTH:
        return title
    cut = title[: MAX_TITLE_LENGTH - 1]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip(" ,;:.-") + "…"


@dataclass(frozen=True)
class AssistantReply:
    """What gets saved for one answer.

    Plain values only, so the database layer does not depend on the RAG code
    or on the API schemas.
    """

    content: str
    status: str
    refusal_reason: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    best_score: float | None = None
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] | None = None  # the Critic's verdict (None for a refusal)


@dataclass(frozen=True)
class SessionSummary:
    """A session as shown in the session list."""

    session: ChatSession
    message_count: int


class SessionRepository:
    """Every database operation on sessions, their messages and their documents."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self) -> ChatSession:
        """Create an empty session, with no title yet."""
        chat_session = ChatSession()
        self._session.add(chat_session)
        self._session.commit()
        return chat_session

    def get(self, session_id: str) -> ChatSession | None:
        """Return the session, or None if the id is unknown."""
        return self._session.get(ChatSession, session_id)

    def list_all(self) -> list[SessionSummary]:
        """Return every session with its number of messages, most recently used first."""
        message_count = (
            select(func.count(Message.id))
            .where(Message.session_id == ChatSession.id)
            .correlate(ChatSession)
            .scalar_subquery()
        )
        statement = select(ChatSession, message_count).order_by(
            ChatSession.updated_at.desc(), ChatSession.created_at.desc()
        )
        return [
            SessionSummary(session=chat_session, message_count=count)
            for chat_session, count in self._session.execute(statement)
        ]

    def list_messages(self, session_id: str) -> list[Message]:
        """Return the messages of a session, in conversation order."""
        statement = (
            select(Message).where(Message.session_id == session_id).order_by(Message.position)
        )
        return list(self._session.scalars(statement))

    def document_ids(self, session_id: str) -> list[str]:
        """Return the ids of the documents selected in the session."""
        statement = (
            select(SessionDocument.document_id)
            .where(SessionDocument.session_id == session_id)
            .order_by(SessionDocument.document_id)
        )
        return list(self._session.scalars(statement))

    def add_exchange(
        self,
        chat_session: ChatSession,
        *,
        question: str,
        document_ids: Sequence[str],
        reply: AssistantReply,
        mode: MessageMode = MessageMode.ASK,
    ) -> tuple[Message, Message]:
        """Save a question, its answer and the selected documents, all at once.

        A single commit: either everything is saved, or nothing is.
        The first question also becomes the session title.
        """
        position = len(chat_session.messages)
        question_message = Message(
            position=position,
            role=MessageRole.USER,
            mode=mode,
            content=question,
        )
        answer_message = Message(
            position=position + 1,
            role=MessageRole.ASSISTANT,
            mode=mode,
            content=reply.content,
            sources=list(reply.sources),
            agent_trace=list(reply.agent_trace),
            status=reply.status,
            refusal_reason=reply.refusal_reason,
            invalid_citations=list(reply.invalid_citations),
            warnings=list(reply.warnings),
            best_score=reply.best_score,
            review=reply.review,
        )
        chat_session.messages.extend([question_message, answer_message])
        self._replace_documents(chat_session, document_ids)
        if chat_session.title is None:
            chat_session.title = make_session_title(question)
        chat_session.updated_at = utc_now()
        self._session.commit()
        return question_message, answer_message

    def _replace_documents(self, chat_session: ChatSession, document_ids: Sequence[str]) -> None:
        # Keep only ids of documents that still exist (an unknown id would
        # break the foreign key), without duplicates, in the given order.
        wanted = list(dict.fromkeys(document_ids))
        existing = (
            set(self._session.scalars(select(Document.id).where(Document.id.in_(wanted))))
            if wanted
            else set()
        )
        # Delete the old links first: re-adding a pair that still exists
        # would break the (session_id, document_id) primary key.
        chat_session.document_links.clear()
        self._session.flush()
        chat_session.document_links.extend(
            SessionDocument(document_id=document_id)
            for document_id in wanted
            if document_id in existing
        )