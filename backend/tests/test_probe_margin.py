"""The score-gap measurement script: filtering, classification, judging and reuse."""

import json

import httpx2
import pytest

from app.agents.critic import Critic
from app.agents.writer import Writer
from app.retrieval.retriever import RetrievedPassage
from scripts.probe_margin import (
    WRITER_CASES,
    Outcome,
    SearchRow,
    WriterCase,
    classify,
    gap_label,
    judge,
    keep_passages,
    normalize,
    outcomes_by_gap,
    run_plan,
    search,
    search_summary,
    writer_summary,
)
from tests.conftest import FakeLLMProvider

MIN_SCORE = 0.44


def passage(chunk_id: str, score: float, page: int = 4, filename: str = "contract.pdf"):
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        filename=filename,
        page_number=page,
        position=0,
        text=f"Text of {chunk_id}: the notice period is 60 days.",
        score=score,
    )


TOP_5 = [
    passage("a", 0.62, page=4),
    passage("b", 0.59, page=4),
    passage("c", 0.55, page=3),
    passage("d", 0.47, page=2),
    passage("e", 0.40, page=1),
]


def ids(passages) -> list[str]:
    return [p.chunk_id for p in passages]


def test_gap_label() -> None:
    assert gap_label(None) == "none"
    assert gap_label(0.05) == "0.05"


def test_no_gap_keeps_every_passage_above_the_threshold() -> None:
    assert ids(keep_passages(TOP_5, MIN_SCORE, None)) == ["a", "b", "c", "d"]


def test_a_gap_keeps_only_the_passages_near_the_best() -> None:
    assert ids(keep_passages(TOP_5, MIN_SCORE, 0.05)) == ["a", "b"]
    assert ids(keep_passages(TOP_5, MIN_SCORE, 0.01)) == ["a"]


def test_a_passage_exactly_at_the_gap_is_kept() -> None:
    passages = [passage("a", 0.60), passage("b", 0.55)]
    assert ids(keep_passages(passages, MIN_SCORE, 0.05)) == ["a", "b"]


def test_a_gap_never_turns_a_threshold_refusal_into_an_answer() -> None:
    below = [passage("a", 0.43), passage("b", 0.42)]
    assert keep_passages(below, MIN_SCORE, None) == []
    assert keep_passages(below, MIN_SCORE, 0.05) == []


def test_classify_answerable_questions() -> None:
    assert classify(TOP_5, "contract.pdf", (4,), MIN_SCORE, 0.05) == (2, "right")
    # Page 2 passes the threshold alone, but is far from the best score.
    assert classify(TOP_5, "contract.pdf", (2,), MIN_SCORE, None) == (4, "right")
    assert classify(TOP_5, "contract.pdf", (2,), MIN_SCORE, 0.05) == (2, "LOST")
    # Page 1 is below the threshold: the gap is not the cause.
    assert classify(TOP_5, "contract.pdf", (1,), MIN_SCORE, 0.05) == (2, "missing")
    # The right page in another file does not count.
    assert classify(TOP_5, "other.pdf", (4,), MIN_SCORE, None) == (4, "missing")


def test_classify_questions_the_documents_cannot_answer() -> None:
    assert classify(TOP_5, "contract.pdf", (), MIN_SCORE, 0.05) == (2, "passed")
    assert classify([passage("a", 0.30)], "contract.pdf", (), MIN_SCORE, 0.05) == (0, "refused")


def test_search_summary() -> None:
    gaps = (None, 0.05)
    rows = [
        SearchRow("contract", "q1", True, {None: (4, "right"), 0.05: (2, "right")}),
        SearchRow("contract", "q2", True, {None: (4, "right"), 0.05: (2, "LOST")}),
        SearchRow("contract", "q3", True, {None: (2, "missing"), 0.05: (1, "missing")}),
        SearchRow("contract", "q4", False, {None: (0, "refused"), 0.05: (0, "refused")}),
        SearchRow("contract", "q5", False, {None: (3, "passed"), 0.05: (1, "passed")}),
    ]
    lines = search_summary(rows, gaps)
    assert lines[1].split() == ["none", "3.3", "2", "of", "3", "0", "1"]
    assert lines[2].split() == ["0.05", "1.7", "1", "of", "3", "1", "1"]
    assert lines[3].startswith("Absent information refused by the threshold: 1 of 2")


NOTICE = WriterCase("notice?", "en", ("60 days", "60 jours"), ("30 days", "30 jours"))
ABSENT = WriterCase("revenue?", "en", None)


def test_normalize_handles_french_spaces_and_case() -> None:
    assert normalize("17\u202f100,00\xa0USD\n Total") == "17 100,00 usd total"


def test_judge_an_answer() -> None:
    assert judge(NOTICE, Outcome(5, answer="The notice period is 60 days [contract.pdf, p. 4]."))
    assert judge(NOTICE, Outcome(5, answer="Le préavis est de 60\u00a0jours."))
    assert not judge(NOTICE, Outcome(5, answer="It is 60 days, or 30 days for breach."))
    assert not judge(NOTICE, Outcome(5, answer="It is 90 days."))
    assert not judge(NOTICE, Outcome(5, refused="model"))
    assert not judge(NOTICE, Outcome(5, refused="error: down"))


def test_judge_a_question_without_answer_in_the_documents() -> None:
    assert judge(ABSENT, Outcome(0, refused="threshold"))
    assert judge(ABSENT, Outcome(5, refused="model"))
    assert not judge(ABSENT, Outcome(5, answer="Revenue was USD 45,370.00."))
    assert not judge(ABSENT, Outcome(5, refused="error: down"))


def test_every_writer_case_has_an_expected_answer_or_a_refusal() -> None:
    for case in WRITER_CASES:
        assert case.language in ("en", "fr")
        assert case.expected is None or case.expected
        # A forbidden text must not also be an expected one.
        assert not set(case.forbidden) & set(case.expected or ())


def agents(llm: FakeLLMProvider) -> tuple[Writer, Critic]:
    return Writer(llm), Critic(llm, use_model=True)


def test_run_plan_answers_and_reviews() -> None:
    llm = FakeLLMProvider()
    llm.replies = ["The notice period is 60 days [S1].", json.dumps({"unsupported": []})]
    writer, critic = agents(llm)
    outcome = run_plan(writer, critic, "notice?", [passage("a", 0.62)])
    assert outcome.refused is None
    assert outcome.answer == "The notice period is 60 days [contract.pdf, p. 4]."
    assert outcome.sources == ["contract.pdf p.4"]
    assert outcome.issues == []
    assert len(llm.calls) == 2  # Writer, then the Critic's model check


def test_run_plan_reports_critic_issues() -> None:
    llm = FakeLLMProvider()
    llm.replies = ["The notice period is 90 days [S1].", json.dumps({"unsupported": [1]})]
    writer, critic = agents(llm)
    outcome = run_plan(writer, critic, "notice?", [passage("a", 0.62)])
    assert "unsupported_number (code)" in outcome.issues
    assert "unsupported_claim (model)" in outcome.issues


def test_run_plan_refusals_and_errors() -> None:
    llm = FakeLLMProvider()
    writer, critic = agents(llm)
    assert run_plan(writer, critic, "q", []).refused == "threshold"
    assert llm.calls == []  # no passage: no model call

    llm.replies = ["NOT_FOUND"]
    assert run_plan(writer, critic, "q", [passage("a", 0.62)]).refused == "model"

    llm.unavailable = True
    failed = run_plan(writer, critic, "q", [passage("a", 0.62)]).refused
    assert failed is not None and failed.startswith("error: ")


def test_outcomes_by_gap_reuses_the_answer_for_the_same_passages() -> None:
    llm = FakeLLMProvider()
    # Two different sets of passages: none -> a, b, c, d; 0.05 and 0.03 -> a, b.
    llm.replies = [
        "It is 60 days or 30 days [S1].",
        json.dumps({"unsupported": []}),
        "It is 60 days [S1].",
        json.dumps({"unsupported": []}),
    ]
    writer, critic = agents(llm)
    outcomes = outcomes_by_gap(writer, critic, "notice?", TOP_5, MIN_SCORE, (None, 0.05, 0.03))
    assert len(llm.calls) == 4
    assert outcomes[None].passages == 4
    assert outcomes[0.05].passages == 2
    assert outcomes[0.05] is outcomes[0.03]
    assert not judge(NOTICE, outcomes[None])
    assert judge(NOTICE, outcomes[0.05])


def test_writer_summary() -> None:
    notice = {
        None: Outcome(4, answer="60 days or 30 days", issues=["x (model)"], seconds=6.0),
        0.05: Outcome(2, answer="60 days", seconds=4.0),
    }
    absent = {
        None: Outcome(4, refused="model", seconds=2.0),
        0.05: Outcome(1, refused="model", seconds=1.5),
    }
    results = [(NOTICE, notice), (ABSENT, absent)]
    lines = writer_summary(results, (None, 0.05))
    assert lines[1].split() == ["none", "1", "of", "2", "1", "8.0s"]
    assert lines[2].split() == ["0.05", "2", "of", "2", "0", "5.5s"]


def test_search_sends_the_documents_and_reads_the_passages() -> None:
    sent: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        result = {
            "chunk_id": "a",
            "document_id": "doc-1",
            "filename": "contract.pdf",
            "page_number": 4,
            "position": 0,
            "text": "60 days",
            "score": 0.62,
        }
        return httpx2.Response(200, json={"query": "q", "results": [result]})

    with httpx2.Client(base_url="http://test", transport=httpx2.MockTransport(handler)) as client:
        passages = search(client, "notice?", 5, ["doc-1"])
        search(client, "notice?", 5, None)
    assert sent[0] == {"query": "notice?", "top_k": 5, "document_ids": ["doc-1"]}
    assert sent[1]["document_ids"] is None
    assert passages == [passage_from("a", 0.62)]


def passage_from(chunk_id: str, score: float) -> RetrievedPassage:
    return RetrievedPassage(chunk_id, "doc-1", "contract.pdf", 4, 0, "60 days", score)


def test_search_raises_on_a_server_error() -> None:
    transport = httpx2.MockTransport(lambda request: httpx2.Response(503, json={"detail": "x"}))
    with (
        httpx2.Client(base_url="http://test", transport=transport) as client,
        pytest.raises(httpx2.HTTPStatusError),
    ):
        search(client, "q", 5, None)