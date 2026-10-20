"""Shapes of the JSON received and returned by the API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import DocumentStatus

MAX_QUERY_LENGTH = 1000
MAX_TOP_K = 20


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

    # Surrounding spaces are removed first, so a blank query is refused.
    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_LENGTH)
    ]
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