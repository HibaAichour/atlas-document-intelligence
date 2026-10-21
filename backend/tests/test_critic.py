"""The Critic: code checks on citations and numbers, then one model check."""

import json

from app.agents.critic import SYSTEM_PROMPT, Critic, Issue, numbers_in, split_sentences
from app.rag.citations import resolve_citations
from app.retrieval.retriever import RetrievedPassage


def make_passage(chunk_id: str, page_number: int, text: str) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        filename="contract.pdf",
        page_number=page_number,
        position=0,
        text=text,
        score=0.8,
    )


NOTICE = make_passage("c1", 4, "Either party may terminate with thirty (30) days written notice.")
FEES = make_passage("c2", 2, "The monthly fee is USD 1200, payable within 15 days.")
PASSAGES = [NOTICE, FEES]


def checked(reply: str):
    """The answer as the Writer returns it, citations resolved."""
    return resolve_citations(reply, PASSAGES)


def codes(review) -> list[tuple[str, str]]:
    return [(issue.code, issue.origin) for issue in review.issues]


def test_sentences_are_split_without_breaking_on_page_numbers() -> None:
    answer = checked("The notice is 30 days [S1]. The fee is USD 1200 [S2]. It is fair.")

    sentences = split_sentences(answer)

    assert [(s.text, s.cited) for s in sentences] == [
        ("The notice is 30 days.", True),
        ("The fee is USD 1200.", True),
        ("It is fair.", False),
    ]


def test_numbers_are_compared_without_separators_or_leading_zeros() -> None:
    assert numbers_in("USD 1,200 within 07 days, rate 4.5") == {"1200", "7", "4.5"}


def test_a_supported_answer_is_ok_and_the_model_sees_numbered_sentences(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 30 days [S1]. The fee is USD 1,200 [S2].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert review.verdict == "ok"
    assert review.issues == []
    assert review.model_checked is True
    call = fake_llm.calls[0]
    assert call.json_mode is True
    assert call.temperature == 0.0
    assert call.messages[0].content == SYSTEM_PROMPT
    user = call.messages[1].content
    assert "[S1]\nEither party may terminate" in user
    assert "1. The notice period is 30 days." in user
    assert "2. The fee is USD 1,200." in user
    # The model judges the text, not the citations or the file names.
    assert "contract.pdf" not in user


def test_invented_citations_are_reported(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 30 days [S1][S7].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert review.verdict == "issues"
    assert codes(review) == [("invented_citations", "code")]
    assert "S7" in review.issues[0].message


def test_an_answer_without_citation_is_reported_once(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 30 days. Either party may terminate.")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    # One issue for the whole answer, not one per sentence.
    assert codes(review) == [("no_citation", "code")]


def test_a_sentence_without_citation_is_reported(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 30 days [S1]. This seems quite short. Yes.")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    # "Yes." is too short to need a citation.
    assert review.issues == [
        Issue("uncited_sentence", "code", "no citation", "This seems quite short.")
    ]


def test_a_number_absent_from_the_cited_passages_is_reported(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 45 days [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert codes(review) == [("unsupported_number", "code")]
    assert review.issues[0].message == "not found in the cited passages: 45"
    assert review.issues[0].sentence == "The notice period is 45 days."


def test_page_numbers_of_citations_are_not_taken_for_numbers(fake_llm) -> None:
    """The page number in "p. 4" comes from the citation, not from the passage."""
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("Either party may terminate with written notice [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert answer.text.endswith("[contract.pdf, p. 4].")
    assert review.verdict == "ok"


def test_numbers_are_checked_against_the_cited_passages_only(fake_llm) -> None:
    """15 is in the fees passage, but the sentence cites only the notice passage."""
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("The notice period is 15 days [S1].")

    review = Critic(fake_llm).review_answer(answer, [NOTICE, FEES])

    assert codes(review) == [("unsupported_number", "code")]


def test_sentences_flagged_by_the_model_are_reported(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": [2]}')
    answer = checked("The notice period is 30 days [S1]. Renewal is automatic [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert review.issues == [
        Issue(
            "unsupported_claim",
            "model",
            "the model found no passage supporting this sentence",
            "Renewal is automatic.",
        )
    ]
    assert review.model_checked is True


def test_numbers_outside_the_list_are_ignored_and_each_sentence_is_reported_once(
    fake_llm,
) -> None:
    fake_llm.replies.append('{"unsupported": [1, 1, 0, 9]}')
    answer = checked("The notice period is 30 days [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert codes(review) == [("unsupported_claim", "model")]


def test_an_unusable_model_reply_leaves_the_code_checks(fake_llm) -> None:
    for reply in ["not json", '{"unsupported": "two"}', "[1]", '{"other": []}']:
        fake_llm.replies.append(reply)
        answer = checked("The notice period is 45 days [S1].")

        review = Critic(fake_llm).review_answer(answer, PASSAGES)

        assert review.model_checked is False
        assert codes(review) == [("unsupported_number", "code")]


def test_a_model_that_is_down_does_not_fail_the_review(fake_llm) -> None:
    fake_llm.unavailable = True
    answer = checked("The notice period is 30 days [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert review.verdict == "ok"
    assert review.model_checked is False


def test_without_the_model_check_the_model_is_not_called(fake_llm) -> None:
    answer = checked("The notice period is 30 days [S1].")

    review = Critic(fake_llm, use_model=False).review_answer(answer, PASSAGES)

    assert review.verdict == "ok"
    assert review.model_checked is False
    assert fake_llm.calls == []


def test_the_review_has_a_json_shape_and_a_trace_summary(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": [1]}')
    answer = checked("The notice period is 45 days [S1].")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert json.loads(json.dumps(review.to_dict())) == {
        "verdict": "issues",
        "issues": [
            {
                "code": "unsupported_number",
                "origin": "code",
                "message": "not found in the cited passages: 45",
                "sentence": "The notice period is 45 days.",
            },
            {
                "code": "unsupported_claim",
                "origin": "model",
                "message": "the model found no passage supporting this sentence",
                "sentence": "The notice period is 45 days.",
            },
        ],
        "model_checked": True,
    }
    assert review.summary() == "2 issues (1 by code, 1 by model), model checked"