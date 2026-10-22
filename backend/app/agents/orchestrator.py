"""Orchestrator: runs a fixed plan of steps for each mode, and records the trace.

The plan is an explicit list of step names. The Orchestrator runs them in
order; a step can end the plan early (a refusal), and the remaining steps
are then recorded as skipped. Routing is rule-based: the user chooses the
mode, no LLM decides. In V2, replanning will change these lists after the
Critic's verdict, without changing the agents.

Plans:
- ask:     retrieval (tool) -> writer -> critic
- extract: analyst -> extractor -> critic
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.agents.analyst import DocumentAnalyst, DocumentProfile, DocumentType
from app.agents.critic import Critic, Review, appears_in, review_extraction
from app.agents.extractor import ExtractionResult, Extractor
from app.agents.fields import FIELDS
from app.agents.trace import AgentRun, StepKind, StepNote, TraceRecorder
from app.agents.writer import Writer
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.models import PageText
from app.llm.base import LLMError
from app.rag.answering import AnswerResult, AnswerWarning, RefusalReason, refusal
from app.rag.citations import Citation, CitationResult, source_label
from app.retrieval.retriever import RetrievedPassage, Retriever

Mode = Literal["ask", "extract"]
ExtractStatus = Literal["extracted", "refused"]

UNSUPPORTED_DOCUMENT_MESSAGE = (
    "This document is neither an invoice nor a contract, so no fields were extracted."
)


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    kind: StepKind


@dataclass(frozen=True, slots=True)
class Plan:
    """The ordered steps run for one mode."""

    mode: Mode
    steps: tuple[Step, ...]


ASK_PLAN = Plan(
    mode="ask",
    steps=(Step("retrieval", "tool"), Step(Writer.name, "agent"), Step(Critic.name, "agent")),
)
EXTRACT_PLAN = Plan(
    mode="extract",
    steps=(
        Step(DocumentAnalyst.name, "agent"),
        Step(Extractor.name, "agent"),
        Step(Critic.name, "agent"),
    ),
)
PLANS: dict[Mode, Plan] = {"ask": ASK_PLAN, "extract": EXTRACT_PLAN}


@dataclass(slots=True)
class _AskState:
    """What the steps of the ask plan share while it runs."""

    repository: DocumentRepository
    question: str
    top_k: int
    document_ids: Sequence[str] | None
    passages: list[RetrievedPassage] = field(default_factory=list)
    best_score: float | None = None
    checked: CitationResult | None = None  # the Writer's answer, for the Critic
    result: AnswerResult | None = None
    stop_reason: str = ""  # set when a step ends the plan early (a refusal)

    @property
    def ended(self) -> bool:
        return self.stop_reason != ""

    def refuse(self, reason: RefusalReason, why: str) -> None:
        """End the plan with a refusal; the remaining steps are skipped."""
        self.result = refusal(self.question, reason, self.best_score)
        self.stop_reason = why


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """One extracted field, with the passage of the document it comes from."""

    name: str
    label: str
    value: str | None
    page: int | None
    source: Citation | None  # the chunk of that page holding the value, if found

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape saved in messages.extraction (the source as in the API)."""
        source = None
        if self.source is not None:
            passage = self.source.passage
            source = {
                "label": self.source.label,
                "display": self.source.display,
                "chunk_id": passage.chunk_id,
                "document_id": passage.document_id,
                "filename": passage.filename,
                "page_number": passage.page_number,
                "position": passage.position,
                "text": passage.text,
                "score": passage.score,
            }
        return {
            "name": self.name,
            "label": self.label,
            "value": self.value,
            "page": self.page,
            "source": source,
        }


@dataclass(frozen=True, slots=True)
class ExtractOutcome:
    """What an extraction produces, ready to be saved and returned by the API."""

    document_id: str
    filename: str
    status: ExtractStatus
    document_type: DocumentType  # "other" for a refusal
    fields: list[ExtractedValue]
    review: Review | None  # None for a refusal
    trace: list[AgentRun]

    @property
    def message(self) -> str:
        """The text shown for this result, written by the code."""
        if self.status == "refused":
            return UNSUPPORTED_DOCUMENT_MESSAGE
        found = sum(1 for value in self.fields if value.value is not None)
        return (
            f"Extracted {found} of {len(self.fields)} fields from {self.filename} "
            f"({self.document_type})."
        )

    def extraction_dict(self) -> dict[str, Any] | None:
        """The JSON shape saved in messages.extraction; None for a refusal."""
        if self.status == "refused":
            return None
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "document_type": self.document_type,
            "fields": [value.to_dict() for value in self.fields],
        }


@dataclass(slots=True)
class _ExtractState:
    """What the steps of the extract plan share while it runs."""

    pages: list[PageText]
    chunks_by_page: dict[int, list[RetrievedPassage]]
    profile: DocumentProfile | None = None
    chosen: list[PageText] = field(default_factory=list)  # pages given to the Extractor
    extraction: ExtractionResult | None = None
    review: Review | None = None
    stop_reason: str = ""  # set when a step ends the plan early (a refusal)

    @property
    def ended(self) -> bool:
        return self.stop_reason != ""


class Orchestrator:
    """Runs the plan of a mode, step by step, and returns the result with its trace."""

    def __init__(
        self,
        retriever: Retriever,
        writer: Writer,
        critic: Critic,
        analyst: DocumentAnalyst,
        extractor: Extractor,
        *,
        min_score: float,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retriever = retriever
        self._writer = writer
        self._critic = critic
        self._analyst = analyst
        self._extractor = extractor
        self._min_score = min_score
        self._clock = clock
        self._ask_steps: dict[str, Callable[[_AskState, StepNote], None]] = {
            "retrieval": self._retrieve,
            Writer.name: self._write,
            Critic.name: self._review,
        }
        self._extract_steps: dict[str, Callable[[_ExtractState, StepNote], None]] = {
            DocumentAnalyst.name: self._analyze,
            Extractor.name: self._extract,
            Critic.name: self._review_extraction,
        }

    def plan(self, mode: Mode) -> Plan:
        """The plan run for this mode (fixed in V1)."""
        return PLANS[mode]

    def ask(
        self,
        repository: DocumentRepository,
        question: str,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> AnswerResult:
        """Answer the question from the documents, citing them, or refuse.

        Raises:
            RetrievalError: If the search cannot run (embedding service down).
            LLMError: If the language model fails or gives no usable answer.
        """
        trace = TraceRecorder(self._clock)
        state = _AskState(repository, question, top_k, document_ids)
        self._run(self.plan("ask"), state, self._ask_steps, trace)
        # Every plan ends with a result; this guards against a plan without one.
        if state.result is None:
            raise RuntimeError("The ask plan ended without a result")
        return replace(state.result, trace=trace.runs)

    def extract(self, repository: DocumentRepository, document: Document) -> ExtractOutcome:
        """Extract the key fields of a ready document, each with its page and source.

        Raises:
            ValueError: If the document has no extracted page.
            LLMError: If the language model fails or gives no usable extraction.
        """
        pages = [
            PageText(page_number=page.page_number, text=page.text, ocr_used=page.ocr_used)
            for page in repository.list_pages(document.id)
        ]
        if not pages:
            raise ValueError("The document has no extracted page")
        chunks_by_page: dict[int, list[RetrievedPassage]] = {}
        for chunk in repository.list_chunks(document.id):
            chunks_by_page.setdefault(chunk.page_number, []).append(
                RetrievedPassage(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    filename=document.filename,
                    page_number=chunk.page_number,
                    position=chunk.position,
                    text=chunk.text,
                    score=1.0,  # not a search result: the page was read in full
                )
            )

        trace = TraceRecorder(self._clock)
        state = _ExtractState(pages, chunks_by_page)
        self._run(self.plan("extract"), state, self._extract_steps, trace)

        if state.ended or state.extraction is None:
            return ExtractOutcome(
                document.id, document.filename, "refused", "other", [], None, trace.runs
            )
        values = [
            ExtractedValue(
                extracted.name,
                extracted.label,
                extracted.value,
                extracted.page,
                self._source_of(state, extracted.name, extracted.value, extracted.page),
            )
            for extracted in state.extraction.fields
        ]
        return ExtractOutcome(
            document.id,
            document.filename,
            "extracted",
            state.extraction.document_type,
            values,
            state.review,
            trace.runs,
        )

    def _run(self, plan: Plan, state: Any, steps: dict[str, Any], trace: TraceRecorder) -> None:
        """Run the steps of the plan in order; once a step ends it, skip the rest.

        Shared by both plans: each state has a stop_reason and an "ended" flag.
        """
        for step in plan.steps:
            if state.ended:
                trace.skip(step.name, step.kind, state.stop_reason)
                continue
            with trace.step(step.name, step.kind) as note:
                steps[step.name](state, note)

    # Steps of the ask plan.

    def _retrieve(self, state: _AskState, note: StepNote) -> None:
        passages = self._retriever.search(
            state.repository, state.question, state.top_k, state.document_ids
        )
        state.best_score = max((passage.score for passage in passages), default=None)
        # Only passages above the threshold reach the model: fewer distractors
        # for a small model, and no LLM call at all when nothing is relevant.
        state.passages = [p for p in passages if p.score >= self._min_score]
        best = "none" if state.best_score is None else f"{state.best_score:.2f}"
        note.summary = (
            f"{len(state.passages)} of {len(passages)} passages kept "
            f"(threshold {self._min_score:.2f}, best {best})"
        )
        if not state.passages:
            state.refuse("no_relevant_passages", "no passage above the relevance threshold")

    def _write(self, state: _AskState, note: StepNote) -> None:
        written = self._writer.write(state.question, state.passages)
        if written.refused or written.answer is None:
            note.status = "refused"
            note.summary = "the passages do not contain the answer (NOT_FOUND)"
            state.refuse("not_found_by_model", "the Writer refused to answer")
            return

        checked = written.answer
        if not checked.text:
            # The reply contained only invented citations: nothing to show.
            raise LLMError("The language model returned no usable answer")

        warnings: list[AnswerWarning] = []
        if checked.invalid_labels:
            warnings.append("invalid_citations_removed")
        if not checked.citations:
            warnings.append("no_valid_citation")
        note.summary = (
            f"{len(checked.citations)} citations, {len(checked.invalid_labels)} invented removed"
        )
        state.checked = checked
        state.result = AnswerResult(
            question=state.question,
            status="answered",
            answer=checked.text,
            citations=checked.citations,
            invalid_citations=checked.invalid_labels,
            warnings=warnings,
            best_score=state.best_score,
        )

    def _review(self, state: _AskState, note: StepNote) -> None:
        # The Critic reports; it never changes the answer (no replanning in V1).
        if state.checked is None or state.result is None:
            raise RuntimeError("The Critic runs after a written answer")
        review = self._critic.review_answer(state.checked, state.passages)
        note.summary = review.summary()
        state.result = replace(state.result, review=review)

    # Steps of the extract plan.

    def _analyze(self, state: _ExtractState, note: StepNote) -> None:
        profile = self._analyst.analyze(state.pages)
        state.profile = profile
        note.summary = profile.summary()
        if profile.document_type == "other":
            note.status = "refused"
            state.stop_reason = "the document is neither an invoice nor a contract"
            return
        state.chosen = [page for page in state.pages if page.page_number in profile.pages]

    def _extract(self, state: _ExtractState, note: StepNote) -> None:
        if state.profile is None or state.profile.document_type == "other":
            raise RuntimeError("The Extractor runs after the Analyst found a supported type")
        state.extraction = self._extractor.extract(state.profile.document_type, state.chosen)
        note.summary = state.extraction.summary()

    def _review_extraction(self, state: _ExtractState, note: StepNote) -> None:
        if state.extraction is None:
            raise RuntimeError("The Critic runs after an extraction")
        state.review = review_extraction(state.extraction, state.chosen)
        count = len(state.review.issues)
        note.summary = ("no issue" if count == 0 else f"{count} issues") + " (code checks)"

    def _source_of(
        self, state: _ExtractState, name: str, value: str | None, page: int | None
    ) -> Citation | None:
        """The chunk of the given page that holds the value, as a clickable source."""
        if value is None or page is None or state.extraction is None:
            return None
        specs = {spec.name: spec for spec in FIELDS[state.extraction.document_type]}
        amount = specs[name].kind == "amount"
        for passage in state.chunks_by_page.get(page, []):
            if appears_in(value, passage.text, amount=amount):
                return Citation(label=name, display=source_label(passage), passage=passage)
        return None