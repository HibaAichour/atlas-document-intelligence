"""Routes for chat sessions: list, create, read, ask a question or extract fields inside one."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import ExtractOutcome, Orchestrator
from app.api.ask import answer_or_error
from app.api.dependencies import get_db, get_orchestrator
from app.api.errors import service_error
from app.api.schemas import (
    AskRequest,
    CitationOut,
    ExtractRequest,
    MessageOut,
    SessionAskResponse,
    SessionOut,
    SessionSummaryOut,
)
from app.core.config import Settings, get_settings
from app.db.models import ChatSession, Document, DocumentStatus, Message, MessageMode
from app.db.repositories import (
    AssistantReply,
    DocumentRepository,
    SessionRepository,
    SessionSummary,
)
from app.llm.base import LLMError
from app.rag.answering import AnswerResult

router = APIRouter(prefix="/sessions", tags=["sessions"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AppOrchestrator = Annotated[Orchestrator, Depends(get_orchestrator)]

SESSION_NOT_FOUND = "Session not found."
DOCUMENT_NOT_FOUND = "Document not found."


def get_session_or_404(repository: SessionRepository, session_id: str) -> ChatSession:
    chat_session = repository.get(session_id)
    if chat_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, SESSION_NOT_FOUND)
    return chat_session


def to_reply(result: AnswerResult) -> AssistantReply:
    """Turn a RAG result into the plain values saved in the database.

    Sources are saved in the exact shape returned by the API (CitationOut),
    so a restored answer is read back with the same schema.
    """
    return AssistantReply(
        content=result.answer,
        status=result.status,
        refusal_reason=result.refusal_reason,
        sources=[CitationOut.from_citation(citation).model_dump() for citation in result.citations],
        invalid_citations=list(result.invalid_citations),
        warnings=list(result.warnings),
        best_score=result.best_score,
        agent_trace=[run.to_dict() for run in result.trace],
        review=None if result.review is None else result.review.to_dict(),
    )


def to_extract_reply(outcome: ExtractOutcome) -> AssistantReply:
    """Turn an extraction into the plain values saved in the database.

    The sources of the values live in "extraction" only (one copy per field),
    so "sources" stays empty. A refusal has no extraction and no review.
    """
    refused = outcome.status == "refused"
    return AssistantReply(
        content=outcome.message,
        status="refused" if refused else "answered",
        refusal_reason="unsupported_document" if refused else None,
        agent_trace=[run.to_dict() for run in outcome.trace],
        review=None if outcome.review is None else outcome.review.to_dict(),
        extraction=outcome.extraction_dict(),
    )


def get_ready_document(db: Session, document_id: str) -> Document:
    """Return the document to extract from: 404 if unknown, 409 if not ready."""
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DOCUMENT_NOT_FOUND)
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Document is not ready for extraction (status: {document.status}).",
        )
    return document


def extract_or_error(orchestrator: Orchestrator, db: Session, document: Document) -> ExtractOutcome:
    """Run the extract plan and turn its failures into clear HTTP errors.

    No retrieval runs in this plan, so only the language model can fail:
    429 when an online provider's usage limit was reached, 503 otherwise.
    A ready document with no extracted page cannot be read (409).
    """
    try:
        return orchestrator.extract(DocumentRepository(db), document)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Document has no extracted text to read."
        ) from error
    except LLMError as error:
        raise service_error(error, f"Extraction failed: {error}") from error


def exchange_response(
    chat_session: ChatSession, question: Message, answer: Message
) -> SessionAskResponse:
    """The messages just saved and the updated session summary."""
    summary = SessionSummary(chat_session, message_count=len(chat_session.messages))
    return SessionAskResponse(
        session=SessionSummaryOut.from_summary(summary),
        question=MessageOut.from_message(question),
        answer=MessageOut.from_message(answer),
    )


@router.get("")
def list_sessions(db: DbSession) -> list[SessionSummaryOut]:
    """Return every session, most recently used first."""
    return [SessionSummaryOut.from_summary(s) for s in SessionRepository(db).list_all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(db: DbSession) -> SessionSummaryOut:
    """Create an empty session. Its title comes from its first question."""
    chat_session = SessionRepository(db).create()
    return SessionSummaryOut.from_summary(SessionSummary(chat_session, message_count=0))


@router.get("/{session_id}")
def read_session(session_id: str, db: DbSession) -> SessionOut:
    """Return a session with its messages (and their sources) and its documents."""
    repository = SessionRepository(db)
    chat_session = get_session_or_404(repository, session_id)
    return SessionOut(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        document_ids=repository.document_ids(chat_session.id),
        messages=[MessageOut.from_message(m) for m in repository.list_messages(chat_session.id)],
    )


# Plain "def": the embedding and the LLM calls block, so it runs in a thread pool.
@router.post("/{session_id}/ask")
def ask_in_session(
    session_id: str,
    request: AskRequest,
    db: DbSession,
    settings: AppSettings,
    orchestrator: AppOrchestrator,
) -> SessionAskResponse:
    """Answer like POST /api/ask, then save the question, the answer and the documents.

    A refusal is saved like any answer. On an error 503 or 429 nothing is
    saved, so the question can simply be asked again.
    """
    repository = SessionRepository(db)
    # Checked before calling the model: an unknown session costs no LLM call.
    chat_session = get_session_or_404(repository, session_id)

    top_k = request.top_k or settings.retrieval_top_k
    result = answer_or_error(orchestrator, db, request.question, top_k, request.document_ids)

    if request.document_ids is None:
        # "Every document": record the documents that were actually searchable.
        used_ids = [
            document.id
            for document in DocumentRepository(db).list_all()
            if document.status == DocumentStatus.READY
        ]
    else:
        used_ids = request.document_ids

    question, answer = repository.add_exchange(
        chat_session, question=request.question, document_ids=used_ids, reply=to_reply(result)
    )
    return exchange_response(chat_session, question, answer)


# Plain "def": the LLM calls block, so it runs in a thread pool.
@router.post("/{session_id}/extract")
def extract_in_session(
    session_id: str,
    request: ExtractRequest,
    db: DbSession,
    orchestrator: AppOrchestrator,
) -> SessionAskResponse:
    """Extract the key fields of one document, then save the request and the result.

    The user message is written by the code. A document that is neither an
    invoice nor a contract gives a saved refusal (unsupported_document).
    The documents selected for questions are not changed. On an error 503
    or 429 nothing is saved, so the extraction can simply be run again.
    """
    repository = SessionRepository(db)
    # Both checked before calling the model: a wrong id costs no LLM call.
    chat_session = get_session_or_404(repository, session_id)
    document = get_ready_document(db, request.document_id)

    outcome = extract_or_error(orchestrator, db, document)

    question, answer = repository.add_exchange(
        chat_session,
        question=f"Extract the key fields of {document.filename}",
        document_ids=None,
        reply=to_extract_reply(outcome),
        mode=MessageMode.EXTRACT,
    )
    return exchange_response(chat_session, question, answer)