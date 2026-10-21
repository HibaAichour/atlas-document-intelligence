"""Routes for chat sessions: list, create, read, and ask a question inside one."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.api.ask import answer_or_503
from app.api.dependencies import get_db, get_orchestrator
from app.api.schemas import (
    AskRequest,
    CitationOut,
    MessageOut,
    SessionAskResponse,
    SessionOut,
    SessionSummaryOut,
)
from app.core.config import Settings, get_settings
from app.db.models import ChatSession, DocumentStatus
from app.db.repositories import (
    AssistantReply,
    DocumentRepository,
    SessionRepository,
    SessionSummary,
)
from app.rag.answering import AnswerResult

router = APIRouter(prefix="/sessions", tags=["sessions"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AppOrchestrator = Annotated[Orchestrator, Depends(get_orchestrator)]

SESSION_NOT_FOUND = "Session not found."


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

    A refusal is saved like any answer. On an error 503 nothing is saved,
    so the question can simply be asked again.
    """
    repository = SessionRepository(db)
    # Checked before calling the model: an unknown session costs no LLM call.
    chat_session = get_session_or_404(repository, session_id)

    top_k = request.top_k or settings.retrieval_top_k
    result = answer_or_503(orchestrator, db, request.question, top_k, request.document_ids)

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
    summary = SessionSummary(chat_session, message_count=len(chat_session.messages))
    return SessionAskResponse(
        session=SessionSummaryOut.from_summary(summary),
        question=MessageOut.from_message(question),
        answer=MessageOut.from_message(answer),
    )