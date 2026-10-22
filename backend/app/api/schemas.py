"""Shapes of the JSON received and returned by the API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agents.analyst import DocumentType
from app.agents.critic import IssueCode, IssueOrigin, Review, Verdict
from app.agents.trace import AgentRun, StepKind, StepStatus
from app.db.models import DocumentStatus, Message, MessageMode, MessageRole
from app.db.repositories import SessionSummary
from app.rag.answering import AnswerStatus, AnswerWarning, RefusalReason
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


class ExtractRequest(BaseModel):
    """An extraction of the key fields of one document."""

    document_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


class AgentRunOut(BaseModel):
    """One step of the Orchestrator's plan: which agent or tool ran, and how."""

    name: str  # "retrieval", "writer", ...
    kind: StepKind  # "agent" (calls the LLM) or "tool" (deterministic)
    status: StepStatus  # "ok", "refused", "skipped" or "failed"
    duration_ms: int
    summary: str  # short technical note, e.g. "3 of 5 passages kept"

    @classmethod
    def from_run(cls, run: AgentRun) -> "AgentRunOut":
        return cls(**run.to_dict())


class IssueOut(BaseModel):
    """One problem the Critic found in an answer."""

    code: IssueCode  # e.g. "unsupported_number"; the interface writes its own text
    origin: IssueOrigin  # "code" (a rule) or "model" (the LLM's judgement)
    message: str  # short technical explanation
    sentence: str | None  # the sentence concerned, without its citations
    # For an extraction: the field concerned. Defaults to None so that reviews
    # saved before this field existed are still read back.
    field: str | None = None


class ReviewOut(BaseModel):
    """The Critic's verdict on an answer. It reports problems, it never changes the answer."""

    verdict: Verdict  # "ok" or "issues"
    issues: list[IssueOut]
    model_checked: bool  # False when only the code checks ran

    @classmethod
    def from_review(cls, review: Review | None) -> "ReviewOut | None":
        return None if review is None else cls.model_validate(review.to_dict())


class AskResponse(BaseModel):
    """An answer with its checked sources, or a refusal."""

    question: str
    status: AnswerStatus
    answer: str  # the refusal message when status is "refused"
    refusal_reason: RefusalReason | None
    citations: list[CitationOut]
    invalid_citations: list[str]  # identifiers invented by the model, removed
    warnings: list[AnswerWarning]
    best_score: float | None  # highest retrieval score, None if nothing was found
    review: ReviewOut | None  # the Critic's verdict; None for a refusal
    agent_trace: list[AgentRunOut]  # the steps run, in order (skipped ones included)


class ExtractedFieldOut(BaseModel):
    """One extracted field: its value, its page and the passage it comes from."""

    name: str  # e.g. "invoice_number"
    label: str  # e.g. "Invoice number"
    value: str | None  # None when the field was not found
    page: int | None
    source: CitationOut | None  # the chunk of that page holding the value, if found


class ExtractionOut(BaseModel):
    """The fields extracted from one document."""

    document_id: str
    filename: str
    document_type: DocumentType  # "invoice" or "contract"
    fields: list[ExtractedFieldOut]


class SessionSummaryOut(BaseModel):
    """A session as shown in the session list."""

    id: str
    title: str | None  # None until the first question
    created_at: datetime
    updated_at: datetime
    message_count: int

    @classmethod
    def from_summary(cls, summary: SessionSummary) -> "SessionSummaryOut":
        chat_session = summary.session
        return cls(
            id=chat_session.id,
            title=chat_session.title,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
            message_count=summary.message_count,
        )


class MessageOut(BaseModel):
    """A saved question or answer.

    An answer has the same fields as AskResponse, so the frontend shows a
    restored answer exactly like a live one. For a question, the answer
    fields are empty (status None, no citations). An extraction (mode
    "extract") keeps its fields and their sources in "extraction"; its
    "citations" list stays empty.
    """

    id: str
    position: int
    role: MessageRole
    mode: MessageMode
    content: str  # the question, or the answer text (refusal message if refused)
    status: AnswerStatus | None
    refusal_reason: RefusalReason | None
    citations: list[CitationOut]
    invalid_citations: list[str]
    warnings: list[AnswerWarning]
    best_score: float | None
    review: ReviewOut | None  # the Critic's verdict (None for questions, refusals, old answers)
    agent_trace: list[AgentRunOut]  # the steps run (empty for questions and old answers)
    extraction: ExtractionOut | None  # the extracted fields (extract answers only)
    created_at: datetime

    @classmethod
    def from_message(cls, message: Message) -> "MessageOut":
        # model_validate checks again the values read from the database
        # (plain text and JSON), so a malformed row fails loudly.
        return cls.model_validate(
            {
                "id": message.id,
                "position": message.position,
                "role": message.role,
                "mode": message.mode,
                "content": message.content,
                "status": message.status,
                "refusal_reason": message.refusal_reason,
                "citations": message.sources,
                "invalid_citations": message.invalid_citations,
                "warnings": message.warnings,
                "best_score": message.best_score,
                "review": message.review,
                "agent_trace": message.agent_trace,
                "extraction": message.extraction,
                "created_at": message.created_at,
            }
        )


class SessionOut(BaseModel):
    """A full session: its messages and the documents selected in it."""

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    document_ids: list[str]
    messages: list[MessageOut]


class SessionAskResponse(BaseModel):
    """The request and answer just saved, and the updated session summary.

    Returned by both POST /api/sessions/{id}/ask and /extract: "question" is
    the user's message (for an extraction, written by the code).
    """

    session: SessionSummaryOut
    question: MessageOut
    answer: MessageOut