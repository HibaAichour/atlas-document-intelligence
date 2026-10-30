"""Route to search the indexed documents (semantic search, no LLM)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_retriever
from app.api.errors import service_error
from app.api.schemas import SearchRequest, SearchResponse, SearchResultOut
from app.core.config import Settings, get_settings
from app.db.repositories import DocumentRepository
from app.retrieval.retriever import RetrievalError, Retriever

router = APIRouter(prefix="/search", tags=["search"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AppRetriever = Annotated[Retriever, Depends(get_retriever)]


# Plain "def": computing the query embedding blocks, so it runs in a thread pool.
@router.post("")
def search(
    request: SearchRequest, db: DbSession, settings: AppSettings, retriever: AppRetriever
) -> SearchResponse:
    """Return the passages closest to the query, best first, with their source.

    No relevance threshold yet: the score is returned so it can be calibrated
    before answers are generated (step 6).
    """
    top_k = request.top_k or settings.retrieval_top_k
    try:
        passages = retriever.search(
            DocumentRepository(db), request.query, top_k, request.document_ids
        )
    except RetrievalError as error:
        raise service_error(error, str(error)) from error
    return SearchResponse(
        query=request.query,
        results=[SearchResultOut.model_validate(passage) for passage in passages],
    )