"""Answer a question from the indexed documents, with checked citations (RAG).

Three guards, all in the code:
1. No passage reaches the relevance threshold: refusal without calling the LLM.
2. The Writer replies NOT_FOUND: refusal, with a message written by the code.
3. Cited identifiers are checked: invented ones are removed and reported.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.agents.writer import Writer
from app.db.repositories import DocumentRepository
from app.llm.base import LLMError
from app.rag.citations import Citation
from app.retrieval.retriever import Retriever

REFUSAL_MESSAGE = "I could not find this information in the available documents."

AnswerStatus = Literal["answered", "refused"]
RefusalReason = Literal["no_relevant_passages", "not_found_by_model"]
AnswerWarning = Literal["invalid_citations_removed", "no_valid_citation"]


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """The outcome of one question, ready to be returned by the API."""

    question: str
    status: AnswerStatus
    answer: str  # text shown to the user (the refusal message when refused)
    refusal_reason: RefusalReason | None = None
    citations: list[Citation] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)  # e.g. ["S9"]
    warnings: list[AnswerWarning] = field(default_factory=list)
    best_score: float | None = None  # highest retrieval score, None if nothing found


class QuestionAnswerer:
    """Retrieval, relevance threshold, Writer, citation check.

    At step 9 the Orchestrator's "ask" plan will run these same pieces;
    this class keeps them together until then.
    """

    def __init__(self, retriever: Retriever, writer: Writer, *, min_score: float) -> None:
        self._retriever = retriever
        self._writer = writer
        self._min_score = min_score

    def answer(
        self,
        repository: DocumentRepository,
        question: str,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> AnswerResult:
        """Answer the question from the documents, or refuse.

        Raises:
            RetrievalError: If the search cannot run (embedding service down).
            LLMError: If the language model fails or gives no usable answer.
        """
        passages = self._retriever.search(repository, question, top_k, document_ids)
        best_score = max((passage.score for passage in passages), default=None)

        # Only passages above the threshold reach the model: fewer distractors
        # for a small model, and no LLM call at all when nothing is relevant.
        relevant = [passage for passage in passages if passage.score >= self._min_score]
        if not relevant:
            return self._refusal(question, "no_relevant_passages", best_score)

        written = self._writer.write(question, relevant)
        if written.refused or written.answer is None:
            return self._refusal(question, "not_found_by_model", best_score)

        checked = written.answer
        if not checked.text:
            # The reply contained only invented citations: nothing to show.
            raise LLMError("The language model returned no usable answer")

        warnings: list[AnswerWarning] = []
        if checked.invalid_labels:
            warnings.append("invalid_citations_removed")
        if not checked.citations:
            warnings.append("no_valid_citation")
        return AnswerResult(
            question=question,
            status="answered",
            answer=checked.text,
            citations=checked.citations,
            invalid_citations=checked.invalid_labels,
            warnings=warnings,
            best_score=best_score,
        )

    @staticmethod
    def _refusal(
        question: str, reason: RefusalReason, best_score: float | None
    ) -> AnswerResult:
        return AnswerResult(
            question=question,
            status="refused",
            answer=REFUSAL_MESSAGE,
            refusal_reason=reason,
            best_score=best_score,
        )