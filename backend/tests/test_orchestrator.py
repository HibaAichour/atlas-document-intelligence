"""The Orchestrator's ask plan: threshold, Writer refusal, Critic, citation warnings, trace.

These tests took over from the QuestionAnswerer tests: the behaviour is the
same, and each result now carries the trace of the steps that ran.
"""

from collections.abc import Sequence
from typing import cast

import pytest

from app.agents.critic import Critic
from app.agents.orchestrator import ASK_PLAN, Orchestrator
from app.agents.writer import Writer
from app.db.repositories import DocumentRepository
from app.llm.base import LLMError
from app.rag.answering import REFUSAL_MESSAGE
from app.retrieval.retriever import RetrievalError, RetrievedPassage, Retriever

QUESTION = "What is the termination notice period?"
# The stub retriever below ignores the repository, so no database is needed.
REPOSITORY = cast(DocumentRepository, object())


class StubRetriever(Retriever):
    """Returns fixed passages and records how it was called."""

    def __init__(self, passages: list[RetrievedPassage], *, down: bool = False) -> None:
        self.passages = passages
        self.down = down
        self.calls: list[tuple[str, int, Sequence[str] | None]] = []

    def search(
        self,
        repository: DocumentRepository,
        query: str,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedPassage]:
        self.calls.append((query, top_k, document_ids))
        if self.down:
            raise RetrievalError("Search failed: connection refused")
        return self.passages


class StepClock:
    """A clock that moves forward 10 ms each time it is read."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.010
        return self.now


def make_passage(chunk_id: str, page_number: int, text: str, score: float) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        filename="contract.pdf",
        page_number=page_number,
        position=0,
        text=text,
        score=score,
    )


NOTICE = make_passage("c1", 4, "Either party may terminate with 30 days written notice.", 0.81)
START = make_passage("c2", 2, "The agreement starts on 1 March 2026.", 0.62)
WEAK = make_passage("c3", 7, "The office is located in Paris.", 0.40)


def make_orchestrator(
    passages, fake_llm, min_score: float = 0.5, *, down: bool = False, critic_model: bool = False
):
    """An Orchestrator on fixed passages. The Critic's model check is off unless
    asked, so each test scripts only the Writer's reply."""
    retriever = StubRetriever(passages, down=down)
    orchestrator = Orchestrator(
        retriever,
        Writer(fake_llm),
        Critic(fake_llm, use_model=critic_model),
        min_score=min_score,
        clock=StepClock(),
    )
    return orchestrator, retriever


def steps(result) -> list[tuple[str, str, str]]:
    """The trace as (name, kind, status), easy to compare."""
    return [(run.name, run.kind, run.status) for run in result.trace]


def test_the_ask_plan_is_an_explicit_list_of_steps(fake_llm) -> None:
    orchestrator, _ = make_orchestrator([], fake_llm)

    plan = orchestrator.plan("ask")

    assert plan is ASK_PLAN
    assert [(step.name, step.kind) for step in plan.steps] == [
        ("retrieval", "tool"),
        ("writer", "agent"),
        ("critic", "agent"),
    ]


def test_no_passage_means_refusal_without_calling_the_model(fake_llm) -> None:
    orchestrator, _ = make_orchestrator([], fake_llm)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "no_relevant_passages"
    assert result.answer == REFUSAL_MESSAGE
    assert result.best_score is None
    assert fake_llm.calls == []


def test_passages_below_the_threshold_mean_refusal_and_a_skipped_writer(fake_llm) -> None:
    orchestrator, _ = make_orchestrator([WEAK], fake_llm, min_score=0.5)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "no_relevant_passages"
    assert result.best_score == pytest.approx(0.40)
    assert result.citations == []
    assert fake_llm.calls == []
    assert steps(result) == [
        ("retrieval", "tool", "ok"),
        ("writer", "agent", "skipped"),
        ("critic", "agent", "skipped"),
    ]
    assert result.trace[0].summary == "0 of 1 passages kept (threshold 0.50, best 0.40)"
    assert result.trace[1].summary == "no passage above the relevance threshold"
    assert result.trace[1].duration_ms == 0
    assert result.review is None


def test_only_passages_above_the_threshold_reach_the_writer(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S1].")
    orchestrator, _ = make_orchestrator([NOTICE, START, WEAK], fake_llm, min_score=0.6)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    prompt = fake_llm.calls[0].messages[1].content
    assert NOTICE.text in prompt
    assert START.text in prompt
    assert WEAK.text not in prompt
    assert result.status == "answered"
    assert result.best_score == pytest.approx(0.81)
    assert result.trace[0].summary == "2 of 3 passages kept (threshold 0.60, best 0.81)"


def test_a_score_equal_to_the_threshold_is_kept(fake_llm) -> None:
    fake_llm.replies.append("It starts on 1 March 2026 [S1].")
    orchestrator, _ = make_orchestrator([START], fake_llm, min_score=0.62)

    result = orchestrator.ask(REPOSITORY, "When does it start?", top_k=5)

    assert result.status == "answered"


def test_a_cited_answer_has_its_sources_no_warning_and_a_full_trace(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S1].")
    orchestrator, retriever = make_orchestrator([NOTICE, START], fake_llm)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=3, document_ids=["doc-1"])

    assert retriever.calls == [(QUESTION, 3, ["doc-1"])]
    assert result.status == "answered"
    assert result.refusal_reason is None
    assert result.answer == "The notice period is 30 days [contract.pdf, p. 4]."
    assert [c.passage.chunk_id for c in result.citations] == ["c1"]
    assert result.warnings == []
    assert result.invalid_citations == []
    assert steps(result) == [
        ("retrieval", "tool", "ok"),
        ("writer", "agent", "ok"),
        ("critic", "agent", "ok"),
    ]
    # The clock moves 10 ms per reading: each step lasts exactly 10 ms.
    assert [run.duration_ms for run in result.trace] == [10, 10, 10]
    assert result.trace[1].summary == "1 citations, 0 invented removed"
    assert result.review is not None
    assert result.review.verdict == "ok"
    assert result.trace[2].summary == "no issue (0 by code, 0 by model), model check unavailable"


def test_a_refusal_by_the_model_uses_the_code_message(fake_llm) -> None:
    fake_llm.replies.append("NOT_FOUND")
    orchestrator, _ = make_orchestrator([NOTICE, START], fake_llm)

    result = orchestrator.ask(REPOSITORY, "What is the CEO's salary?", top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "not_found_by_model"
    assert result.answer == REFUSAL_MESSAGE
    assert result.citations == []
    assert len(fake_llm.calls) == 1
    assert steps(result) == [
        ("retrieval", "tool", "ok"),
        ("writer", "agent", "refused"),
        ("critic", "agent", "skipped"),
    ]
    assert result.trace[2].summary == "the Writer refused to answer"
    assert result.review is None


def test_invented_citations_are_removed_with_a_warning(fake_llm) -> None:
    fake_llm.replies.append("The notice is 30 days [S1]. Renewal is automatic [S8].")
    orchestrator, _ = make_orchestrator([NOTICE, START], fake_llm)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.answer == "The notice is 30 days [contract.pdf, p. 4]. Renewal is automatic."
    assert result.invalid_citations == ["S8"]
    assert result.warnings == ["invalid_citations_removed"]
    assert result.trace[1].summary == "1 citations, 1 invented removed"
    # The Critic reports the problem without changing the answer.
    assert result.review is not None
    assert [issue.code for issue in result.review.issues] == [
        "invented_citations",
        "uncited_sentence",
    ]


def test_an_answer_without_valid_citation_is_returned_with_a_warning(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days.")
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.answer == "The notice period is 30 days."
    assert result.warnings == ["no_valid_citation"]


def test_only_invented_citations_give_both_warnings(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S5].")
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.warnings == ["invalid_citations_removed", "no_valid_citation"]


def test_a_reply_made_only_of_invented_citations_is_an_error(fake_llm) -> None:
    fake_llm.replies.append("[S9]")
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm)

    with pytest.raises(LLMError, match="no usable answer"):
        orchestrator.ask(REPOSITORY, QUESTION, top_k=5)


def test_a_model_that_is_down_raises_llm_error(fake_llm) -> None:
    fake_llm.unavailable = True
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm)

    with pytest.raises(LLMError):
        orchestrator.ask(REPOSITORY, QUESTION, top_k=5)


def test_a_search_that_fails_raises_retrieval_error_without_calling_the_model(
    fake_llm,
) -> None:
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm, down=True)

    with pytest.raises(RetrievalError, match="connection refused"):
        orchestrator.ask(REPOSITORY, QUESTION, top_k=5)
    assert fake_llm.calls == []


def test_the_critic_checks_the_answer_with_the_model_and_never_changes_it(fake_llm) -> None:
    fake_llm.replies.extend(["The notice period is 45 days [S1].", '{"unsupported": [1]}'])
    orchestrator, _ = make_orchestrator([NOTICE], fake_llm, critic_model=True)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.answer == "The notice period is 45 days [contract.pdf, p. 4]."
    assert result.review is not None
    assert result.review.verdict == "issues"
    assert result.review.model_checked is True
    assert [(issue.code, issue.origin) for issue in result.review.issues] == [
        ("unsupported_number", "code"),
        ("unsupported_claim", "model"),
    ]
    # Writer, then Critic: two calls, the second one in JSON mode.
    assert [call.json_mode for call in fake_llm.calls] == [False, True]
    assert result.trace[2].summary == "2 issues (1 by code, 1 by model), model checked"


def test_a_model_down_during_the_critic_keeps_the_answer(fake_llm) -> None:
    """The Writer answered; the model then fails: the answer is still returned."""

    class FailsSecondCall(type(fake_llm)):
        def generate(self, messages, *, temperature=0.0, json_mode=False):
            if json_mode:
                self.unavailable = True
            return super().generate(messages, temperature=temperature, json_mode=json_mode)

    llm = FailsSecondCall()
    llm.replies.append("The notice period is 30 days [S1].")
    orchestrator, _ = make_orchestrator([NOTICE], llm, critic_model=True)

    result = orchestrator.ask(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.review is not None
    assert result.review.model_checked is False
    assert steps(result)[2] == ("critic", "agent", "ok")