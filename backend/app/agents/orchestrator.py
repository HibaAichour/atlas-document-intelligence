"""Orchestrator: runs a fixed plan of steps for each mode, and records the trace.

The plan is an explicit list of step names. The Orchestrator runs them in
order; a step can end the plan early (a refusal), and the remaining steps
are then recorded as skipped. Routing is rule-based: the user chooses the
mode, no LLM decides. In V2, replanning will change this list after the
Critic's verdict, without changing the agents.

Plans:
- ask: retrieval (tool) -> writer          (the Critic is added at step 9.2)
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from app.agents.trace import StepKind, StepNote, TraceRecorder
from app.agents.writer import Writer
from app.db.repositories import DocumentRepository
from app.llm.base import LLMError
from app.rag.answering import AnswerResult, AnswerWarning, refusal
from app.retrieval.retriever import RetrievedPassage, Retriever

Mode = Literal["ask"]  # "extract" arrives at step 9.4


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    kind: StepKind


@dataclass(frozen=True, slots=True)
class Plan:
    """The ordered steps run for one mode."""

    mode: Mode
    steps: tuple[Step, ...]


ASK_PLAN = Plan(mode="ask", steps=(Step("retrieval", "tool"), Step(Writer.name, "agent")))


@dataclass(slots=True)
class _AskState:
    """What the steps of the ask plan share while it runs."""

    repository: DocumentRepository
    question: str
    top_k: int
    document_ids: Sequence[str] | None
    passages: list[RetrievedPassage] = field(default_factory=list)
    best_score: float | None = None
    result: AnswerResult | None = None  # set by the step that ends the plan
    stop_reason: str = ""  # why the plan ended early, shown for the skipped steps

    @property
    def finished(self) -> bool:
        return self.result is not None


class Orchestrator:
    """Runs the plan of a mode, step by step, and returns the result with its trace."""

    def __init__(
        self,
        retriever: Retriever,
        writer: Writer,
        *,
        min_score: float,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retriever = retriever
        self._writer = writer
        self._min_score = min_score
        self._clock = clock
        self._ask_steps: dict[str, Callable[[_AskState, StepNote], None]] = {
            "retrieval": self._retrieve,
            Writer.name: self._write,
        }

    def plan(self, mode: Mode) -> Plan:
        """The plan run for this mode (fixed in V1)."""
        return ASK_PLAN

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
        for step in self.plan("ask").steps:
            if state.finished:
                trace.skip(step.name, step.kind, state.stop_reason)
                continue
            with trace.step(step.name, step.kind) as note:
                self._ask_steps[step.name](state, note)

        # The last step always sets a result; this guards against a plan without one.
        if state.result is None:
            raise RuntimeError("The ask plan ended without a result")
        return replace(state.result, trace=trace.runs)

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
            state.result = refusal(state.question, "no_relevant_passages", state.best_score)
            state.stop_reason = "no passage above the relevance threshold"

    def _write(self, state: _AskState, note: StepNote) -> None:
        written = self._writer.write(state.question, state.passages)
        if written.refused or written.answer is None:
            note.status = "refused"
            note.summary = "the passages do not contain the answer (NOT_FOUND)"
            state.result = refusal(state.question, "not_found_by_model", state.best_score)
            state.stop_reason = "the Writer refused to answer"
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
        state.result = AnswerResult(
            question=state.question,
            status="answered",
            answer=checked.text,
            citations=checked.citations,
            invalid_citations=checked.invalid_labels,
            warnings=warnings,
            best_score=state.best_score,
        )