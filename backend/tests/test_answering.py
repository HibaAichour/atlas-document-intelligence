"""The question-answering service: threshold, Writer refusal, citation warnings."""

from collections.abc import Sequence
from typing import cast

import pytest

from app.agents.writer import Writer
from app.db.repositories import DocumentRepository
from app.llm.base import LLMError
from app.rag.answering import REFUSAL_MESSAGE, QuestionAnswerer
from app.retrieval.retriever import RetrievedPassage, Retriever

QUESTION = "What is the termination notice period?"
# The stub retriever below ignores the repository, so no database is needed.
REPOSITORY = cast(DocumentRepository, object())


class StubRetriever(Retriever):
    """Returns fixed passages and records how it was called."""

    def __init__(self, passages: list[RetrievedPassage]) -> None:
        self.passages = passages
        self.calls: list[tuple[str, int, Sequence[str] | None]] = []

    def search(
        self,
        repository: DocumentRepository,
        query: str,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedPassage]:
        self.calls.append((query, top_k, document_ids))
        return self.passages


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


def make_answerer(passages, fake_llm, min_score: float = 0.5):
    retriever = StubRetriever(passages)
    return QuestionAnswerer(retriever, Writer(fake_llm), min_score=min_score), retriever


def test_no_passage_means_refusal_without_calling_the_model(fake_llm) -> None:
    answerer, _ = make_answerer([], fake_llm)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "no_relevant_passages"
    assert result.answer == REFUSAL_MESSAGE
    assert result.best_score is None
    assert fake_llm.calls == []


def test_passages_below_the_threshold_mean_refusal_without_calling_the_model(
    fake_llm,
) -> None:
    answerer, _ = make_answerer([WEAK], fake_llm, min_score=0.5)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "no_relevant_passages"
    assert result.best_score == pytest.approx(0.40)
    assert result.citations == []
    assert fake_llm.calls == []


def test_only_passages_above_the_threshold_reach_the_writer(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S1].")
    answerer, _ = make_answerer([NOTICE, START, WEAK], fake_llm, min_score=0.6)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    prompt = fake_llm.calls[0].messages[1].content
    assert NOTICE.text in prompt
    assert START.text in prompt
    assert WEAK.text not in prompt
    assert result.status == "answered"
    assert result.best_score == pytest.approx(0.81)


def test_a_score_equal_to_the_threshold_is_kept(fake_llm) -> None:
    fake_llm.replies.append("It starts on 1 March 2026 [S1].")
    answerer, _ = make_answerer([START], fake_llm, min_score=0.62)

    result = answerer.answer(REPOSITORY, "When does it start?", top_k=5)

    assert result.status == "answered"


def test_a_cited_answer_has_its_sources_and_no_warning(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S1].")
    answerer, retriever = make_answerer([NOTICE, START], fake_llm)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=3, document_ids=["doc-1"])

    assert retriever.calls == [(QUESTION, 3, ["doc-1"])]
    assert result.status == "answered"
    assert result.refusal_reason is None
    assert result.answer == "The notice period is 30 days [contract.pdf, p. 4]."
    assert [c.passage.chunk_id for c in result.citations] == ["c1"]
    assert result.warnings == []
    assert result.invalid_citations == []


def test_a_refusal_by_the_model_uses_the_code_message(fake_llm) -> None:
    fake_llm.replies.append("NOT_FOUND")
    answerer, _ = make_answerer([NOTICE, START], fake_llm)

    result = answerer.answer(REPOSITORY, "What is the CEO's salary?", top_k=5)

    assert result.status == "refused"
    assert result.refusal_reason == "not_found_by_model"
    assert result.answer == REFUSAL_MESSAGE
    assert result.citations == []
    assert len(fake_llm.calls) == 1


def test_invented_citations_are_removed_with_a_warning(fake_llm) -> None:
    fake_llm.replies.append("The notice is 30 days [S1]. Renewal is automatic [S8].")
    answerer, _ = make_answerer([NOTICE, START], fake_llm)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.answer == "The notice is 30 days [contract.pdf, p. 4]. Renewal is automatic."
    assert result.invalid_citations == ["S8"]
    assert result.warnings == ["invalid_citations_removed"]


def test_an_answer_without_valid_citation_is_returned_with_a_warning(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days.")
    answerer, _ = make_answerer([NOTICE], fake_llm)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    assert result.status == "answered"
    assert result.answer == "The notice period is 30 days."
    assert result.warnings == ["no_valid_citation"]


def test_only_invented_citations_give_both_warnings(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S5].")
    answerer, _ = make_answerer([NOTICE], fake_llm)

    result = answerer.answer(REPOSITORY, QUESTION, top_k=5)

    assert result.warnings == ["invalid_citations_removed", "no_valid_citation"]


def test_a_reply_made_only_of_invented_citations_is_an_error(fake_llm) -> None:
    fake_llm.replies.append("[S9]")
    answerer, _ = make_answerer([NOTICE], fake_llm)

    with pytest.raises(LLMError, match="no usable answer"):
        answerer.answer(REPOSITORY, QUESTION, top_k=5)


def test_a_model_that_is_down_raises_llm_error(fake_llm) -> None:
    fake_llm.unavailable = True
    answerer, _ = make_answerer([NOTICE], fake_llm)

    with pytest.raises(LLMError):
        answerer.answer(REPOSITORY, QUESTION, top_k=5)