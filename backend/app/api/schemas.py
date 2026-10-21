"""Shapes of the JSON received and returned by the API."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import DocumentStatus
from app.rag.citations import Citation

MAX_QUERY_LENGTH = 1000
MAX_TOP_K = 20

# Surrounding spaces are removed first, so a blank text is refused.
QueryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_LENGTH)
]


class DocumentOut(BaseModel):
    """A document as shown in the document list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    mime_type: str
    page_count: int
    ocr_used: bool
    status: DocumentStatus
    error: str | None
    created_at: datetime


class PageOut(BaseModel):
    """The extracted text of one page."""

    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    ocr_used: bool


class SearchRequest(BaseModel):
    """A semantic search over the indexed documents."""

    query: QueryText
    # None means "use the default from the settings" (RETRIEVAL_TOP_K).
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)
    # None searches every document; a list limits the search to those documents.
    document_ids: list[str] | None = None


class SearchResultOut(BaseModel):
    """One passage found by the search, with its source."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    position: int
    text: str
    score: float  # cosine similarity: higher means closer to the query


class SearchResponse(BaseModel):
    """The passages found for a query, best first."""

    query: str
    results: list[SearchResultOut]


class AskRequest(BaseModel):
    """A question answered from the indexed documents (RAG)."""

    question: QueryText
    # None means "use the default from the settings" (RETRIEVAL_TOP_K).
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)
    # None uses every document; a list limits the answer to those documents.
    document_ids: list[str] | None = None


class CitationOut(BaseModel):
    """A passage cited by the answer: what is shown and where it comes from."""

    label: str  # identifier used by the model, e.g. "S1"
    display: str  # text shown in the answer, e.g. "[contract.pdf, p. 3]"
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    position: int
    text: str
    score: float

    @classmethod
    def from_citation(cls, citation: Citation) -> "CitationOut":
        passage = citation.passage
        return cls(
            label=citation.label,
            display=citation.display,
            chunk_id=passage.chunk_id,
            document_id=passage.document_id,
            filename=passage.filename,
            page_number=passage.page_number,
            position=passage.position,
            text=passage.text,
            score=passage.score,
        )


class AskResponse(BaseModel):
    """An answer with its checked sources, or a refusal."""

    question: str
    status: Literal["answered", "refused"]
    answer: str  # the refusal message when status is "refused"
    refusal_reason: Literal["no_relevant_passages", "not_found_by_model"] | None
    citations: list[CitationOut]
    invalid_citations: list[str]  # identifiers invented by the model, removed
    warnings: list[Literal["invalid_citations_removed", "no_valid_citation"]]
    best_score: float | None  # highest retrieval score, None if nothing was found