"""What a question produces: an answer with checked citations, or a refusal.

The steps that build it (retrieval, Writer, Critic) are run by the
Orchestrator (app.agents.orchestrator); this module only holds the result
types and the refusal message, shared by the Orchestrator and the API.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.agents.critic import Review
from app.agents.trace import AgentRun
from app.rag.citations import Citation

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
    review: Review | None = None  # the Critic's verdict; None for a refusal
    trace: list[AgentRun] = field(default_factory=list)  # steps run by the Orchestrator


def refusal(question: str, reason: RefusalReason, best_score: float | None) -> AnswerResult:
    """A refusal, with the message written by the code (never by the model)."""
    return AnswerResult(
        question=question,
        status="refused",
        answer=REFUSAL_MESSAGE,
        refusal_reason=reason,
        best_score=best_score,
    )