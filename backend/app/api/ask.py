"""Route to ask a question about the indexed documents (RAG with citations)."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.api.dependencies import get_db, get_orchestrator
from app.api.schemas import AgentRunOut, AskRequest, AskResponse, CitationOut
from app.core.config import Settings, get_settings
from app.db.repositories import DocumentRepository
from app.llm.base import LLMError
from app.rag.answering import AnswerResult
from app.retrieval.retriever import RetrievalError

router = APIRouter(prefix="/ask", tags=["ask"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AppOrchestrator = Annotated[Orchestrator, Depends(get_orchestrator)]


def answer_or_503(
    orchestrator: Orchestrator,
    db: Session,
    question: str,
    top_k: int,
    document_ids: Sequence[str] | None,
) -> AnswerResult:
    """Run the ask plan and turn an unreachable service into an error 503.

    Shared by POST /api/ask and POST /api/sessions/{id}/ask, so both routes
    refuse and fail in exactly the same way.
    """
    try:
        return orchestrator.ask(DocumentRepository(db), question, top_k, document_ids)
    except RetrievalError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except LLMError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Answer generation failed: {error}"
        ) from error


# Plain "def": the embedding and the LLM calls block, so it runs in a thread pool.
@router.post("")
def ask(
    request: AskRequest, db: DbSession, settings: AppSettings, orchestrator: AppOrchestrator
) -> AskResponse:
    """Answer the question from the documents, citing document and page, or refuse.

    A refusal is a normal answer (status 200, status "refused"). An error 503
    means the embedding service or the language model could not be reached.
    Nothing is saved: use POST /api/sessions/{id}/ask to keep the conversation.
    """
    top_k = request.top_k or settings.retrieval_top_k
    result = answer_or_503(orchestrator, db, request.question, top_k, request.document_ids)

    return AskResponse(
        question=result.question,
        status=result.status,
        answer=result.answer,
        refusal_reason=result.refusal_reason,
        citations=[CitationOut.from_citation(citation) for citation in result.citations],
        invalid_citations=result.invalid_citations,
        warnings=result.warnings,
        best_score=result.best_score,
        agent_trace=[AgentRunOut.from_run(run) for run in result.trace],
    )