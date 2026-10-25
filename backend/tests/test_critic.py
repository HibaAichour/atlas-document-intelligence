"""The Critic: code checks on citations and numbers, then one model check."""

import json

import pytest

from app.agents.critic import (
    SYSTEM_PROMPT,
    Critic,
    Issue,
    appears_in,
    number_readings,
    numbers_in,
    split_sentences,
    unsupported_numbers,
)
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


def test_citations_after_the_final_full_stop_belong_to_the_sentence() -> None:
    """The Writer sometimes cites after the full stop: "... 1,200. [S2]"."""
    answer = checked("The monthly fee is USD 1,200.00. [S2][S1]")

    sentences = split_sentences(answer)

    assert [(s.text, s.cited) for s in sentences] == [("The monthly fee is USD 1,200.00.", True)]


def test_citations_after_a_full_stop_inside_the_answer_stay_with_their_sentence() -> None:
    answer = checked("The notice is 30 days. [S1] The fee is USD 1200. [S2] It is fair.")

    sentences = split_sentences(answer)

    assert [(s.text, s.cited) for s in sentences] == [
        ("The notice is 30 days.", True),
        ("The fee is USD 1200.", True),
        ("It is fair.", False),
    ]


def test_a_sentence_without_citation_before_a_cited_one_is_still_reported(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    answer = checked("This seems quite short. The notice period is 30 days. [S1]")

    review = Critic(fake_llm).review_answer(answer, PASSAGES)

    assert review.issues == [
        Issue("uncited_sentence", "code", "no citation", "This seems quite short.")
    ]


def test_numbers_are_compared_without_separators_or_leading_zeros() -> None:
    # "1,200" is 1200 in English and 1.2 in French: both readings are kept.
    assert numbers_in("USD 1,200 within 07 days, rate 4.5") == {"1200", "1.2", "7", "4.5"}


@pytest.mark.parametrize(
    ("written", "values"),
    [
        ("45,370.00", {"45370"}),  # English
        ("45 370,00", {"45370"}),  # French, normal space
        ("45\u00a0370,00", {"45370"}),  # French, no-break space
        ("45\u202f370,00", {"45370"}),  # French, narrow no-break space
        ("45.370,00", {"45370"}),  # French, dot for thousands
        ("1 234 567,50", {"1234567.5"}),
        ("99.38", {"99.38"}),
        ("99,38", {"99.38"}),
        ("1,5", {"1.5"}),
        ("15950.00", {"15950"}),
        ("12,500", {"12500", "12.5"}),  # ambiguous
        ("1.500", {"1.5", "1500"}),  # ambiguous
        ("1,200,000", {"1200000"}),
        ("07", {"7"}),
        ("1.2.3", {"123"}),
    ],
)
def test_number_readings_in_english_and_french(written: str, values: set[str]) -> None:
    assert number_readings(written) == frozenset(values)


def test_a_french_amount_is_one_number() -> None:
    assert numbers_in("Le total s'élève à 45 370,00 USD.") == {"45370"}
    # Separate numbers stay separate: a space only joins groups of three digits.
    assert numbers_in("le 14 mai 2026, 4 h 37 min") == {"14", "2026", "4", "37"}


def test_unsupported_numbers_keep_the_written_form() -> None:
    known = numbers_in("The fee is USD 12,500 and the rate 99.38%.")

    assert unsupported_numbers("99,38 % et 12 500 USD", known) == []
    assert unsupported_numbers("45 370,00 USD, puis 45 370,00", known) == ["45 370,00"]


def test_amounts_appear_in_either_format() -> None:
    assert appears_in("USD 15,950.00", "Total 15 950,00 USD", amount=True)
    assert appears_in("15 950,00", "Total USD 15,950.00", amount=True)
    assert not appears_in("USD 15,590.00", "Total USD 15,950.00", amount=True)
    assert not appears_in("no number", "Total USD 15,950.00", amount=True)


def _passage(text: str) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id="c1",
        document_id="d1",
        filename="review.pptx",
        page_number=2,
        position=0,
        text=text,
        score=0.7,
    )


def test_a_french_answer_from_an_english_passage_is_not_flagged(fake_llm) -> None:
    # Measured at step 10 bis: "99,38%" written from "99.38%" was flagged.
    fake_llm.replies.append('{"unsupported": []}')
    passages = [_passage("May 2026 | 99.38% | 99.5% | 2 | 1 h 25 min")]
    answer = resolve_citations(
        "La disponibilité de la plateforme en mai 2026 était de 99,38%. [S1]", passages
    )

    review = Critic(fake_llm).review_answer(answer, passages)

    assert review.issues == []


def test_a_wrong_number_in_french_is_still_flagged(fake_llm) -> None:
    fake_llm.replies.append('{"unsupported": []}')
    passages = [_passage("Total invoiced in Q2 2026: USD 45,370.00.")]
    answer = resolve_citations("Le total facturé au T2 2026 est de 45 730,00 USD [S1].", passages)

    review = Critic(fake_llm).review_answer(answer, passages)

    assert codes(review) == [("unsupported_number", "code")]
    assert review.issues[0].message == "not found in the cited passages: 45 730,00"


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
                "field": None,
            },
            {
                "code": "unsupported_claim",
                "origin": "model",
                "message": "the model found no passage supporting this sentence",
                "sentence": "The notice period is 45 days.",
                "field": None,
            },
        ],
        "model_checked": True,
    }
    assert review.summary() == "2 issues (1 by code, 1 by model), model checked"